"""Recommendation evidence, never a usage cap or a billing meter."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import insert
from ..models.campaign_review import CampaignReview
from ..models.project import Project
from ..models.asset import AssetVersion, ProcessingStatus
from ..models.upload_request import RequestUpload, UploadRequest
from .campaign_access import context, TELEHEALTH, ENDS_AT_TIMESTAMP
from . import review_bridge


def successful_assets(reviews):
    return {r['asset_id'] for r in reviews if r.get('review_state') in ('clear', 'held') and r.get('version_id')}


def recommendation(count):
    return 'team' if count >= 20 else 'masterclass'


def record_successes(db, user, asset_ids):
    campaign = context(user)
    if not campaign or not asset_ids:
        return
    rows = [{'id': uuid.uuid4(), 'user_id': user.id, 'campaign_id': campaign['id'],
             'asset_id': uuid.UUID(str(asset_id))} for asset_id in set(asset_ids)]
    db.execute(insert(CampaignReview).values(rows).on_conflict_do_nothing(constraint='uq_campaign_review_asset'))
    # Caller owns the transaction: a review read can run while finish_request
    # holds FOR UPDATE. Committing here would release that lock prematurely.
    db.flush()


def record_request_successes(db, req, reviews):
    assets = successful_assets(reviews)
    if not assets:
        return
    project = db.get(Project, req.project_id)
    if project is None:
        return
    from ..models.user import User
    user = db.get(User, project.created_by)
    if user is not None and context(user):
        rows = db.query(RequestUpload.asset_id, AssetVersion.id).join(AssetVersion,
            (AssetVersion.asset_id == RequestUpload.asset_id)
            & (AssetVersion.version_number == RequestUpload.version_number)).filter(RequestUpload.request_id == req.id,
            AssetVersion.deleted_at.is_(None),
            RequestUpload.submitted_at >= datetime(2026, 10, 1, tzinfo=timezone.utc),
            RequestUpload.submitted_at < datetime.fromtimestamp(ENDS_AT_TIMESTAMP, timezone.utc)).all()
        eligible = {(str(asset_id), str(version_id)) for asset_id, version_id in rows}
        record_successes(db, user, {r['asset_id'] for r in reviews
            if r['asset_id'] in assets and (r['asset_id'], r.get('version_id')) in eligible})


def refresh_usage(db, user):
    """Read existing engine verdicts only; never submit new reviews from the paywall."""
    if not context(user):
        return 0
    rows = (db.query(RequestUpload.asset_id, AssetVersion.id)
        .join(UploadRequest, RequestUpload.request_id == UploadRequest.id)
        .join(Project, UploadRequest.project_id == Project.id)
        .join(AssetVersion, (AssetVersion.asset_id == RequestUpload.asset_id)
              & (AssetVersion.version_number == RequestUpload.version_number))
        .filter(Project.created_by == user.id, Project.deleted_at.is_(None),
                RequestUpload.submitted_at.isnot(None),
                RequestUpload.submitted_at >= datetime(2026, 10, 1, tzinfo=timezone.utc),
                RequestUpload.submitted_at < datetime.fromtimestamp(ENDS_AT_TIMESTAMP, timezone.utc),
                AssetVersion.deleted_at.is_(None), AssetVersion.processing_status == ProcessingStatus.ready)
        .all())
    versions = {}
    for asset_id, version_id in rows:
        versions.setdefault(str(asset_id), set()).add(str(version_id))
    stats = review_bridge.asset_stats(list(versions))
    successful = {aid for aid, evidence in stats.items() if evidence.get('reviewed') is True
                  and evidence.get('version_id') in versions.get(aid, set())
                  and type(evidence.get('openMustFix')) is int and evidence['openMustFix'] >= 0}
    record_successes(db, user, successful)
    db.commit()
    return db.query(CampaignReview).filter(CampaignReview.user_id == user.id,
        CampaignReview.campaign_id == TELEHEALTH['id'], CampaignReview.deleted_at.is_(None)).count()
