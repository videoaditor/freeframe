"""Private assignment preparation; public gate remains metadata-only."""
import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from ..database import get_db
from ..middleware.auth import get_current_user
from ..models.user import User
from ..models.project import Project, ProjectRole
from ..models.checklist_binding import ChecklistBinding
from ..services import review_bridge
from ..services.checklists import reserve_binding, binding_out, dispatch_binding
from ..services.permissions import require_project_role

router = APIRouter(tags=['checklists'])


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
    if not re.fullmatch(r'[a-f0-9]{24}', str(card.get('card_id', ''))):
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
