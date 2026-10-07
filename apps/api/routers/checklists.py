"""Private assignment preparation; public gate remains metadata-only."""
import re
import secrets
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..middleware.auth import bearer_scheme, get_current_user
from ..models.asset import Asset, AssetVersion
from ..models.folder import Folder
from ..models.upload_request import UploadRequest
from ..models.user import User
from ..models.project import Project, ProjectRole
from ..models.checklist_binding import ChecklistBinding
from ..services import review_bridge
from ..services.checklists import reserve_binding, binding_out, dispatch_binding, validate_snapshot
from ..services.permissions import require_project_role, validate_share_link

router = APIRouter(tags=['checklists'])


def require_review_bridge(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    """The existing server-to-server bridge secret is never a user/guest credential."""
    if not settings.review_bridge_secret:
        raise HTTPException(503, 'Review bridge unavailable')
    presented = credentials.credentials if credentials else ''
    if not secrets.compare_digest(presented.encode(), settings.review_bridge_secret.encode()):
        raise HTTPException(401, 'Invalid review bridge credentials')


@router.get('/internal/review/checklist-snapshot', include_in_schema=False,
    dependencies=[Depends(require_review_bridge)])
def read_saved_snapshot(
    response: Response,
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    version_id: uuid.UUID,
    share_token: str = Query(min_length=1, max_length=255),
    db: Session = Depends(get_db),
):
    """Read frozen context for an exact media version; never prepare or reload inputs."""
    missing = HTTPException(404, 'Saved review context not found')
    row = db.query(ChecklistBinding).filter(ChecklistBinding.review_share_token == share_token,
        ChecklistBinding.project_id == project_id, ChecklistBinding.deleted_at.is_(None)).first()
    if row is None or row.project_id != project_id or row.review_share_token != share_token or not row.folder_id:
        raise missing
    project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    folder = db.query(Folder).filter(Folder.id == row.folder_id, Folder.deleted_at.is_(None)).first()
    if project is None or folder is None or folder.project_id != project_id:
        raise missing
    link = validate_share_link(db, share_token)
    if link.folder_id != row.folder_id or link.asset_id is not None or link.project_id not in (None, project_id):
        raise missing
    if link.password_hash or link.visibility != 'public':
        raise missing
    if row.request_id is not None:
        request = db.query(UploadRequest).filter(UploadRequest.id == row.request_id,
            UploadRequest.revoked_at.is_(None)).first()
        if request is None or request.revoked_at is not None or request.project_id != project_id or request.folder_id != row.folder_id or request.review_share_token != share_token:
            raise missing
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.deleted_at.is_(None)).first()
    version = db.query(AssetVersion).filter(AssetVersion.id == version_id,
        AssetVersion.deleted_at.is_(None)).first()
    if asset is None or asset.project_id != project_id or asset.folder_id != row.folder_id or version is None or version.asset_id != asset.id:
        raise missing
    if row.snapshot is None:
        raise missing
    try:
        snapshot = validate_snapshot(row, {'snapshot': row.snapshot, 'context_sha256': row.context_sha256})
    except (ValueError, TypeError):
        raise HTTPException(409, 'Saved review context is invalid')
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Vary'] = 'Authorization'
    return {'schema_version': 'autoreview.saved-snapshot.v1', 'tenant_id': str(project_id),
        'binding_id': str(row.id), 'upload_request_id': str(row.request_id) if row.request_id else None,
        'asset_id': str(asset.id), 'version_id': str(version.id), 'version_number': version.version_number,
        'context_sha256': row.context_sha256, 'snapshot': snapshot}


class ChecklistPrepare(BaseModel):
    project_id: uuid.UUID
    trello_url: str = Field(max_length=2000)

    @field_validator('trello_url')
    @classmethod
    def valid_card(cls, value):
        if not re.match(r'^https://(?:www\.)?trello\.com/c/[A-Za-z0-9]+(?:[/?#]|$)', value):
            raise ValueError('A Trello card link is required')
        return value


@router.post('/checklists', status_code=201)
def prepare_checklist(body: ChecklistPrepare, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if getattr(current_user, 'is_staff', True) is False:
        raise HTTPException(403, 'Staff only')
    project = db.query(Project).filter(Project.id == body.project_id, Project.deleted_at.is_(None)).first()
    if project is None:
        raise HTTPException(404, 'Project not found')
    require_project_role(db, body.project_id, current_user, ProjectRole.editor)
    card = review_bridge.checklist_card(body.trello_url)
    if not card:
        raise HTTPException(503, 'Card could not be verified; upload remains available')
    if not re.fullmatch(r'[a-f0-9]{24}', str(card.get('card_id', ''))) or not re.fullmatch(r'[A-Za-z0-9]{8}', str(card.get('short_link', ''))):
        raise HTTPException(404, 'Card not found')
    from .requests import project_brand
    # Canonical URL ensures short/full links deduplicate against the same immutable intent.
    intent = {'brand': project_brand(db, project), 'title': '', 'brief_text': '',
        'brief_url': f"https://trello.com/c/{card['card_id']}", 'brief_pdf_base64': '',
        'trello_short_link': card.get('short_link', '')}
    binding = reserve_binding(db, body.project_id, current_user.id, f"trello:{card['card_id']}", intent, card['card_id'])
    db.commit()
    dispatch_binding(binding.id)
    return binding_out(binding)


def _authorized(db, binding_id, user, minimum=ProjectRole.viewer):
    row = db.query(ChecklistBinding).filter(ChecklistBinding.id == binding_id, ChecklistBinding.deleted_at.is_(None)).first()
    if row is None:
        raise HTTPException(404, 'Checklist not found')
    project = db.query(Project).filter(Project.id == row.project_id, Project.deleted_at.is_(None)).first()
    if project is None:
        raise HTTPException(404, 'Project not found')
    require_project_role(db, row.project_id, user, minimum)
    return row


@router.get('/checklists/{binding_id}')
def read_checklist(binding_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return binding_out(_authorized(db, binding_id, current_user))


@router.post('/checklists/{binding_id}/retry')
def retry_checklist(binding_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = _authorized(db, binding_id, current_user, ProjectRole.editor)
    row = db.query(ChecklistBinding).filter(ChecklistBinding.id == row.id).with_for_update().one()
    if row.status == 'failed' or getattr(row, 'registration_error', None):
        if row.status == 'failed':
            row.status = 'queued'; row.error_code = None; row.attempts = 0; row.next_attempt_at = datetime.now(timezone.utc)
        row.registration_attempts = 0; row.registration_error = None; row.next_registration_at = None
        db.commit()
        dispatch_binding(row.id)
    return binding_out(row)
