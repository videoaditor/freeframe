"""Resume committed intents after process/broker restarts using existing Celery/beat."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import or_
from .celery_app import celery_app
from ..database import SessionLocal
from ..models.checklist_binding import ChecklistBinding
from ..models.project import Project
from ..models.folder import Folder
from ..models.upload_request import UploadRequest
from ..services import review_bridge
from ..services.checklists import advance_binding


def _register(db, row):
    if row.registered_at or not row.review_share_token:
        return
    if row.request_id:
        req = db.query(UploadRequest).filter(UploadRequest.id == row.request_id, UploadRequest.project_id == row.project_id, UploadRequest.revoked_at.is_(None)).first()
        if req is None:
            return
    if row.folder_id:
        folder = db.query(Folder).filter(Folder.id == row.folder_id, Folder.project_id == row.project_id, Folder.deleted_at.is_(None)).first()
        if folder is None:
            return
    ref = {'tenant_id': str(row.project_id), 'binding_id': str(row.id), 'context_sha256': row.context_sha256,
        'plan_id': row.plan_id, 'content_sha256': row.content_sha256}
    brief = row.snapshot['briefing']['text'] if row.snapshot else row.intent.get('brief_text', '')
    result = review_bridge.register_request(row.review_share_token, row.intent['brand'], row.intent.get('title', ''),
        brief, '' if row.snapshot else row.intent.get('brief_url', ''),
        '' if row.snapshot else row.intent.get('brief_pdf_base64', ''), checklist=ref)
    if result and result.get('ok'):
        row.registered_at = datetime.now(timezone.utc)
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
        if project is None:
            return
        # Preserve ordinary registration even if the optional plan service is unavailable.
        _register(db, row)
        db.refresh(row, with_for_update=True)
        old_plan = row.plan_id
        advance_binding(db, row)
        if row.plan_id != old_plan or row.status == 'ready':
            row.registered_at = None
        _register(db, row)
    finally:
        db.close()


@celery_app.task(name='resume_checklists')
def resume_checklists():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = db.query(ChecklistBinding.id).filter(ChecklistBinding.deleted_at.is_(None),
            or_(ChecklistBinding.status.in_(['queued', 'preparing', 'running']),
                (ChecklistBinding.review_share_token.isnot(None) & ChecklistBinding.registered_at.is_(None))),
            or_(ChecklistBinding.next_attempt_at.is_(None), ChecklistBinding.next_attempt_at <= now)
        ).order_by(ChecklistBinding.created_at).limit(50).all()
    finally:
        db.close()
    for (binding_id,) in rows:
        prepare_checklist.delay(str(binding_id))
