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
    return _saved_envelope(response, row, project_id, asset, version)


def _saved_envelope(response, row, project_id, asset, version):
    if row.snapshot is None:
        raise HTTPException(404, 'Saved review context not found')
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


@router.get('/internal/review/iteration-checklist-snapshot', include_in_schema=False,
    dependencies=[Depends(require_review_bridge)])
def read_iteration_snapshot(response: Response, binding_id: uuid.UUID, project_id: uuid.UUID,
    asset_id: uuid.UUID, version_id: uuid.UUID, share_token: str = Query(min_length=1, max_length=255),
    db: Session = Depends(get_db)):
    """Attest current components or an exact derived recipe, never the whole project."""
    from .requests import request_state
    from ..services.iteration_flow import current_recipes
    missing = HTTPException(404, 'Saved review context not found')
    row = db.query(ChecklistBinding).filter(ChecklistBinding.id == binding_id,
        ChecklistBinding.project_id == project_id, ChecklistBinding.deleted_at.is_(None)).first()
    req = db.query(UploadRequest).filter(UploadRequest.id == row.request_id).first() if row else None
    if req is None or request_state(req, datetime.now(timezone.utc)) != 'live' or req.receive_iterations is not True or req.iteration_mode != 'components':
        raise missing
    if req.project_id != project_id or req.folder_id != row.folder_id or req.review_share_token != row.review_share_token:
        raise missing
    project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    folder = db.query(Folder).filter(Folder.id == req.folder_id, Folder.deleted_at.is_(None)).first()
    if project is None or folder is None or folder.project_id != project_id:
        raise missing
    link = validate_share_link(db, share_token)
    if link.password_hash or link.visibility != 'public' or link.project_id not in (None, project_id):
        raise missing
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.deleted_at.is_(None)).first()
    def current_version(source_id, expected):
        try: source_id = uuid.UUID(str(source_id))
        except (ValueError, TypeError): return None
        source = db.query(Asset).filter(Asset.id == source_id, Asset.project_id == project_id,
            Asset.deleted_at.is_(None)).first()
        latest = db.query(AssetVersion).filter(AssetVersion.asset_id == source_id,
            AssetVersion.deleted_at.is_(None)).order_by(AssetVersion.version_number.desc()).first()
        return latest if source and latest and str(latest.id) == str(expected) else None
    version = current_version(asset_id, version_id)
    if asset is None or version is None:
        raise missing
    state = req.iteration_state or {}
    slots = state.get('slots', {})
    source = any(s.get('asset_id') == str(asset_id) and s.get('version_id') == str(version_id) for s in slots.values())
    if source:
        if share_token != req.review_share_token or link.folder_id != req.folder_id or link.asset_id is not None or asset.folder_id != req.folder_id:
            raise missing
    else:
        if asset.iteration_derived is not True or link.asset_id != asset_id or link.folder_id is not None:
            raise missing
        match = next((recipe for recipe, key in current_recipes(str(req.id), req.iteration_manifest or {'recipes': []}, state, req.iteration_ratio)
            if state.get('outputs', {}).get(key, {}).get('asset_id') == str(asset_id)
            and state['outputs'][key].get('version_id') == str(version_id)
            and state['outputs'][key].get('share_token') == share_token), None)
        if match is None:
            raise missing
        for slot_id in match['slots']:
            slot = slots.get(slot_id, {})
            source_asset = db.query(Asset).filter(Asset.id == uuid.UUID(slot['asset_id']),
                Asset.folder_id == req.folder_id, Asset.deleted_at.is_(None)).first()
            if source_asset is None or current_version(slot.get('asset_id'), slot.get('version_id')) is None:
                raise missing
    return _saved_envelope(response, row, project_id, asset, version)


@router.get('/internal/review/editor-target/{token}', include_in_schema=False,
    dependencies=[Depends(require_review_bridge)])
def editor_target(token: str, response: Response, db: Session = Depends(get_db)):
    """Attest one live assignment for explicit legacy migration; never mint a link."""
    from .requests import request_state, project_brand
    missing = HTTPException(404, 'Editor assignment not found')
    req = db.query(UploadRequest).filter(UploadRequest.token == token).first()
    if req is None or request_state(req, datetime.now(timezone.utc)) != 'live':
        raise missing
    project = db.query(Project).filter(Project.id == req.project_id, Project.deleted_at.is_(None)).first()
    folder = db.query(Folder).filter(Folder.id == req.folder_id, Folder.deleted_at.is_(None)).first()
    if project is None or folder is None or folder.project_id != project.id:
        raise missing
    link = validate_share_link(db, req.review_share_token)
    if link.folder_id != folder.id or link.asset_id is not None or link.project_id not in (None, project.id) or link.password_hash or link.visibility != 'public':
        raise missing
    row = db.query(ChecklistBinding).filter(ChecklistBinding.request_id == req.id,
        ChecklistBinding.project_id == project.id, ChecklistBinding.folder_id == folder.id,
        ChecklistBinding.deleted_at.is_(None)).first()
    if row and row.review_share_token != req.review_share_token:
        raise missing
    card_id = row.trello_card_id if row and re.fullmatch('[a-f0-9]{24}', row.trello_card_id or '') else None
    # A brand-wide link must never acquire a card's private brief through migration.
    intent = row.intent if row else {}
    has_brief = bool(req.brief_excerpt or req.iteration_brief or any((intent or {}).get(k) for k in ('brief_text', 'brief_url', 'brief_pdf_base64')))
    scope = 'card' if card_id else 'brand' if not has_brief else 'unmappable'
    # Existing assignments keep their frozen identity when an owner binds future workspace work.
    from ..services.project_brands import confirmed_brand
    brand = project_brand(db, project)
    if not brand.startswith('cust-') and confirmed_brand(project):
        if not req.brand_slug or (row and (row.intent or {}).get('brand') != req.brand_slug):
            raise missing
        brand = req.brand_slug
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Vary'] = 'Authorization'
    return {'request_id': str(req.id), 'project_id': str(project.id), 'folder_id': str(folder.id),
        'token': req.token, 'url': settings.frontend_url.rstrip('/') + '/r/' + req.token,
        'brand': brand, 'card_id': card_id, 'scope': scope}


class EditorBinding(BaseModel):
    legacy_ref: str = Field(pattern=r'^[ud]:[A-Za-z0-9._-]{1,2048}$')
    token: str = Field(pattern=r'^[A-Za-z0-9_-]{1,255}$')


@router.get('/internal/review/editor-bindings', include_in_schema=False,
    dependencies=[Depends(require_review_bridge)])
def read_editor_binding(response: Response,
    legacy_ref: str = Query(pattern=r'^[ud]:[A-Za-z0-9._-]{1,2048}$'), db: Session = Depends(get_db)):
    """A cache miss is not evidence that an existing capability was never migrated."""
    rows = db.query(UploadRequest).filter(UploadRequest.iteration_state.contains(
        {'legacy_editor_refs': [legacy_ref]})).all()
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Vary'] = 'Authorization'
    if not rows:
        return {'mapped': False}
    if len(rows) != 1:
        raise HTTPException(410, 'Editor assignment is unavailable')
    try:
        target = editor_target(rows[0].token, response, db)
    except HTTPException as error:
        if error.status_code in (403, 404, 410):
            raise HTTPException(410, 'Editor assignment is unavailable') from error
        raise
    saved = (rows[0].iteration_state or {}).get('legacy_editor_targets', {}).get(legacy_ref)
    if saved != target:
        raise HTTPException(410, 'Editor assignment has changed')
    return {'mapped': True, 'target': target}


@router.post('/internal/review/editor-bindings', include_in_schema=False,
    dependencies=[Depends(require_review_bridge)])
def claim_editor_binding(body: EditorBinding, response: Response, db: Session = Depends(get_db)):
    """The database owns canonical identity; Worker KV is only a redirect cache."""
    from copy import deepcopy
    from sqlalchemy import text
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:ref, 0))'),
        {'ref': 'autoreview.editor-binding:' + body.legacy_ref})
    req = db.query(UploadRequest).filter(UploadRequest.token == body.token).with_for_update().first()
    prior = db.query(UploadRequest).filter(UploadRequest.iteration_state.contains(
        {'legacy_editor_refs': [body.legacy_ref]})).first()
    if prior and (req is None or prior.id != req.id):
        raise HTTPException(409, 'Legacy editor link already belongs to another assignment')
    target = editor_target(body.token, response, db)
    state = deepcopy(req.iteration_state or {})
    refs = state.setdefault('legacy_editor_refs', [])
    targets = state.setdefault('legacy_editor_targets', {})
    if body.legacy_ref in targets and targets[body.legacy_ref] != target:
        raise HTTPException(409, 'Editor assignment has changed')
    targets[body.legacy_ref] = target
    if body.legacy_ref not in refs:
        refs.append(body.legacy_ref)
    req.iteration_state = state
    db.commit()
    return {'ok': True, 'request_id': target['request_id']}


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
    project = db.query(Project).filter(Project.id == body.project_id, Project.deleted_at.is_(None)).populate_existing().with_for_update().first()
    if project is None:
        raise HTTPException(404, 'Project not found')
    require_project_role(db, body.project_id, current_user, ProjectRole.editor)
    card = review_bridge.checklist_card(body.trello_url)
    if not card:
        raise HTTPException(503, 'Card could not be verified; upload remains available')
    if not re.fullmatch(r'[a-f0-9]{24}', str(card.get('card_id', ''))) or not re.fullmatch(r'[A-Za-z0-9]{8}', str(card.get('short_link', ''))):
        raise HTTPException(404, 'Card not found')
    from ..services.project_brands import require_project_card
    require_project_card(project, card)
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
