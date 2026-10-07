"""Resume committed intents after process/broker restarts using existing Celery/beat."""
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from sqlalchemy import and_, or_
from .celery_app import celery_app
from ..database import SessionLocal
from ..models.checklist_binding import ChecklistBinding
from ..models.project import Project
from ..models.folder import Folder
from ..models.upload_request import UploadRequest
from ..services import review_bridge
from ..services.checklists import advance_binding


def _retire(db, row):
    row.status = 'failed'
    row.error_code = 'assignment-unavailable'
    row.registration_attempts = 3
    row.registration_error = 'assignment-unavailable'
    row.next_registration_at = None
    row.next_attempt_at = None
    db.commit()


def _register(db, row):
    if row.registered_at or not row.review_share_token or getattr(row, 'registration_attempts', 0) >= 3:
        return
    if getattr(row, 'next_registration_at', None) and row.next_registration_at > datetime.now(timezone.utc):
        return
    ref = {'tenant_id': str(row.project_id), 'binding_id': str(row.id), 'context_sha256': row.context_sha256,
        'plan_id': row.plan_id, 'content_sha256': row.content_sha256}
    brief = row.snapshot['briefing']['text'] if row.snapshot else row.intent.get('brief_text', '')
    url = '' if row.snapshot else row.intent.get('brief_url', '')
    # A project membership does not grant access to Trello's service account.
    # Internal Trello input is resolved only by the verified snapshot path.
    if urlparse(url).hostname in {'trello.com', 'www.trello.com'}:
        url = ''
    result = review_bridge.register_request(row.review_share_token, row.intent['brand'], row.intent.get('title', ''),
        brief, url, '' if row.snapshot else row.intent.get('brief_pdf_base64', ''), checklist=ref)
    if result and result.get('ok'):
        row.registered_at = datetime.now(timezone.utc)
        row.registration_attempts = 0
        row.registration_error = None
        row.next_registration_at = None
    else:
        row.registration_attempts = getattr(row, 'registration_attempts', 0) + 1
        row.registration_error = 'registration-unavailable'
        row.next_registration_at = datetime.now(timezone.utc) + timedelta(seconds=30 * row.registration_attempts) if row.registration_attempts < 3 else None
    db.commit()


@celery_app.task(name='prepare_checklist', acks_late=True)
def prepare_checklist(binding_id):
    db = SessionLocal()
    try:
        row = db.query(ChecklistBinding).filter(ChecklistBinding.id == uuid.UUID(binding_id),
            ChecklistBinding.deleted_at.is_(None)).with_for_update().first()
        if row is None:
            return
        project = db.query(Project).filter(Project.id == row.project_id, Project.deleted_at.is_(None)).first()
        request = db.query(UploadRequest).filter(UploadRequest.id == row.request_id, UploadRequest.project_id == row.project_id, UploadRequest.revoked_at.is_(None)).first() if row.request_id else True
        folder = db.query(Folder).filter(Folder.id == row.folder_id, Folder.project_id == row.project_id, Folder.deleted_at.is_(None)).first() if row.folder_id else True
        if project is None or request is None or folder is None:
            _retire(db, row)
            return
        # Ordinary registration and paid preparation have independent retry budgets.
        _register(db, row)
        db.refresh(row, with_for_update=True)
        advance_binding(db, row)  # Commits pending registration with every changed reference.
        db.refresh(row, with_for_update=True)
        _register(db, row)
    finally:
        db.close()


@celery_app.task(name='resume_checklists')
def resume_checklists():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        plan_due = and_(ChecklistBinding.status.in_(['queued', 'preparing', 'running']),
            or_(ChecklistBinding.next_attempt_at.is_(None), ChecklistBinding.next_attempt_at <= now))
        registration_due = and_(ChecklistBinding.review_share_token.isnot(None), ChecklistBinding.registered_at.is_(None),
            ChecklistBinding.registration_attempts < 3,
            or_(ChecklistBinding.next_registration_at.is_(None), ChecklistBinding.next_registration_at <= now))
        rows = db.query(ChecklistBinding.id).filter(ChecklistBinding.deleted_at.is_(None),
            or_(plan_due, registration_due)).order_by(ChecklistBinding.updated_at, ChecklistBinding.id).limit(50).all()
    finally:
        db.close()
    for (binding_id,) in rows:
        prepare_checklist.delay(str(binding_id))
