"""Small private projection of existing submission evidence; no new DB state."""
import secrets
from ..config import settings
from ..models.asset import AssetVersion
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
