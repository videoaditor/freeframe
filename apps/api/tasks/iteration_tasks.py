"""Durable assembly progresses even after the editor closes the browser."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import or_
from .celery_app import celery_app
from ..config import settings
from ..database import SessionLocal
from ..models.upload_request import UploadRequest
from ..services.iteration_runner import run_step


@celery_app.task(name='advance_iteration_request', soft_time_limit=310, time_limit=330)
def advance_iteration_request(request_id):
    if not settings.iterations_enabled: return
    with SessionLocal() as db:
        changed=run_step(db,uuid.UUID(request_id))
    if changed:
        advance_iteration_request.apply_async(args=[request_id],countdown=2)


@celery_app.task(name='sweep_iteration_requests')
def sweep_iteration_requests():
    if not settings.iterations_enabled: return
    now=datetime.now(timezone.utc)
    # ponytail: scan live requests; add indexed next_run_at if request volume makes this costly.
    with SessionLocal() as db:
        ids=[str(r.id) for r in db.query(UploadRequest).filter(UploadRequest.receive_iterations.is_(True),
            UploadRequest.iteration_mode=='components',UploadRequest.revoked_at.is_(None),
            or_(UploadRequest.expires_at.is_(None),UploadRequest.expires_at>now),
            or_(UploadRequest.iteration_lease_until.is_(None),UploadRequest.iteration_lease_until<now)).all()]
    for request_id in ids:
        advance_iteration_request.delay(request_id)
    return len(ids)
