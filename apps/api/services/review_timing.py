"""Small private projection of existing submission evidence; no new DB state."""
import secrets
import uuid
from datetime import datetime, timezone
from ..config import settings
from ..models.asset import Asset, AssetVersion
from ..models.upload_request import RequestUpload, UploadRequest


def private_timing_context(db, service_key, share_token, asset_id, version_id, project_id, *, service_user=None):
    if not service_user or not settings.service_api_key_email or service_user.email != settings.service_api_key_email:
        return {}
    if not isinstance(service_key, str) or not settings.service_api_key or not secrets.compare_digest(service_key, settings.service_api_key):
        return {}
    version = db.query(AssetVersion).filter(
        AssetVersion.id == version_id, AssetVersion.asset_id == asset_id,
        AssetVersion.deleted_at.is_(None)).first()
    if not version:
        return {}
    upload = db.query(RequestUpload).filter(
        RequestUpload.asset_id == asset_id, RequestUpload.version_number == version.version_number,
        RequestUpload.request_id == UploadRequest.id,
        UploadRequest.review_share_token == share_token, UploadRequest.project_id == project_id,
        UploadRequest.revoked_at.is_(None)).first()
    if not upload or not upload.submitted_at:
        return {}
    return {'timing_context': {'tenant_id': str(project_id), 'submitted_at': upload.submitted_at.isoformat()}}


def iteration_review_progress(db, req, entry, *, source=False):
    """Project Parts facts only; the runner has no durable analysis/publication clock yet."""
    if not entry.get('asset_id') or not entry.get('version_id'):
        return {}
    asset_id, version_id = uuid.UUID(entry['asset_id']), uuid.UUID(entry['version_id'])
    version = db.query(AssetVersion).join(Asset, Asset.id == AssetVersion.asset_id).filter(
        AssetVersion.id == version_id, AssetVersion.asset_id == asset_id,
        AssetVersion.deleted_at.is_(None), Asset.project_id == req.project_id,
        Asset.deleted_at.is_(None)).first()
    progress = {'version_id':str(version_id), 'stage':'failed'}
    if not version:
        return {'review_progress':progress}
    processing = version.processing_status.value
    # Source review can finish before HLS; the runner uses this same durable readiness flag.
    if source and processing == 'processing' and getattr(version,'iteration_review_ready',False) is True:
        processing = 'ready'
    progress['stage'] = ('failed' if entry.get('status') == 'error' or processing == 'failed'
                         else 'done' if entry.get('status') in ('clear','held','delivered') else 'waiting')
    if source:
        upload = db.query(RequestUpload).filter(RequestUpload.request_id == req.id,
            RequestUpload.asset_id == asset_id, RequestUpload.version_number == version.version_number).first()
        if upload and upload.submitted_at:
            submitted = upload.submitted_at
            if submitted.tzinfo is None:
                submitted = submitted.replace(tzinfo=timezone.utc)
            progress.update(queued_at=submitted.isoformat(),
                elapsedSeconds=max(0,(datetime.now(timezone.utc)-submitted).total_seconds()))
    return {'processing':processing, 'version_number':version.version_number, 'review_progress':progress}
