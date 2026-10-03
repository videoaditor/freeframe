"""Campaign boundaries: trusted identity, fixed cutoff and one-brand enforcement."""
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from apps.api.models.user import User, UserStatus
from apps.api.services import campaign_access as campaign


def customer(paid=False):
    return User(id=uuid.uuid4(), name='Owner', email='owner@example.com',
                is_staff=False, is_superadmin=False, status=UserStatus.active,
                suite_account_id='account', suite_brand_id='brand',
                suite_campaign={**campaign.TELEHEALTH, 'state': 'active', 'previewOnly': not paid})


def test_canonical_cutoff_is_inclusive_and_paid_access_survives(monkeypatch):
    user = customer()
    monkeypatch.setattr(campaign.time, 'time', lambda: campaign.ENDS_AT_TIMESTAMP - 1)
    assert not campaign.preview_expired(user)
    monkeypatch.setattr(campaign.time, 'time', lambda: campaign.ENDS_AT_TIMESTAMP)
    assert campaign.preview_expired(user)
    assert not campaign.preview_expired(customer(paid=True))


def test_preferences_cannot_change_or_create_campaign_access():
    user = User(preferences={'suite_campaign': {**campaign.TELEHEALTH, 'previewOnly': True}})
    assert campaign.context(user) is None


def test_malformed_attested_metadata_fails_closed():
    with pytest.raises(HTTPException) as exc:
        campaign.validate_context({**campaign.TELEHEALTH, 'previewOnly': 'false', 'state': 'active'})
    assert exc.value.status_code == 503


def test_one_brand_limit_locks_owner_before_counting(mock_db):
    user = customer()
    mock_db.with_for_update.return_value = mock_db
    mock_db.one.return_value = user
    mock_db.first.return_value = object()
    with pytest.raises(HTTPException) as exc:
        campaign.require_brand_slot(mock_db, user)
    assert exc.value.status_code == 409
    mock_db.with_for_update.assert_called_once()


def test_paid_owner_has_no_preview_brand_limit(mock_db):
    campaign.require_brand_slot(mock_db, customer(paid=True))
    mock_db.query.assert_not_called()


def test_guest_link_of_expired_preview_fails_closed(monkeypatch, mock_db):
    from apps.api.services import whop_auth
    user = customer()
    mock_db.get.return_value = user
    monkeypatch.setattr(campaign.time, 'time', lambda: campaign.ENDS_AT_TIMESTAMP)
    monkeypatch.setattr(whop_auth, 'require_customer_entitlement', MagicMock(side_effect=HTTPException(401, 'missing')))
    with pytest.raises(HTTPException) as exc:
        campaign.require_project_access(mock_db, user.id)
    assert exc.value.status_code == 403
    assert exc.value.detail['code'] == 'campaign_expired'


def test_guest_after_paid_upgrade_is_allowed(monkeypatch, mock_db):
    user = customer(paid=True)
    mock_db.get.return_value = user
    monkeypatch.setattr(campaign.time, 'time', lambda: campaign.ENDS_AT_TIMESTAMP)
    campaign.require_project_access(mock_db, user.id)


@pytest.mark.parametrize('operation', ['presign', 'complete'])
def test_authenticated_editor_cannot_continue_new_upload_after_owner_expiry(mock_db, monkeypatch, operation):
    from apps.api.routers import upload
    from apps.api.models.asset import Asset, AssetVersion, MediaFile, ProcessingStatus
    from apps.api.models.project import Project
    from apps.api.schemas.upload import PresignPartRequest, CompleteUploadRequest
    from fastapi import BackgroundTasks
    owner, editor = customer(), customer()
    project = Project(id=uuid.uuid4(), created_by=owner.id)
    asset = Asset(id=uuid.uuid4(), project_id=project.id)
    version = AssetVersion(id=uuid.uuid4(), asset_id=asset.id, created_by=editor.id, processing_status=ProcessingStatus.uploading)
    media = MediaFile(version_id=version.id, s3_key_raw='raw/owned')
    mock_db.first.side_effect = [media, version] if operation == 'presign' else [version, media]
    mock_db.get.side_effect = lambda model, key: {Asset: asset, Project: project, User: owner}[model]
    monkeypatch.setattr(campaign.time, 'time', lambda: campaign.ENDS_AT_TIMESTAMP)
    post = MagicMock()
    monkeypatch.setattr(upload, 'presign_upload_part', post)
    monkeypatch.setattr(upload, 'complete_multipart_upload', post)
    with pytest.raises(HTTPException) as exc:
        if operation == 'presign':
            upload.presign_part(PresignPartRequest(s3_key='raw/owned', upload_id='u', part_number=1), mock_db, editor)
        else:
            upload.complete_upload(CompleteUploadRequest(s3_key='raw/owned', upload_id='u', asset_id=asset.id, version_id=version.id, parts=[]), BackgroundTasks(), mock_db, editor)
    assert exc.value.detail['code'] == 'campaign_expired'
    post.assert_not_called()


def test_usage_counts_successful_assets_once_across_versions():
    from apps.api.services.campaign_usage import successful_assets, recommendation
    version = str(uuid.uuid4())
    assets = [{'asset_id': 'a', 'version_id': version, 'review_state': 'held'},
              {'asset_id': 'a', 'version_id': str(uuid.uuid4()), 'review_state': 'clear'},
              {'asset_id': 'b', 'version_id': version, 'review_state': 'reviewing'},
              {'asset_id': 'c', 'version_id': version, 'review_state': 'unavailable'}]
    assert successful_assets(assets) == {'a'}
    assert recommendation(19) == 'masterclass'
    assert recommendation(20) == 'team'


def test_invited_editor_cannot_write_to_expired_owner_workspace(mock_db, monkeypatch):
    from apps.api.services import permissions
    from apps.api.models.project import Project, ProjectRole
    owner = customer()
    project = Project(id=uuid.uuid4(), created_by=owner.id)
    editor = User(id=uuid.uuid4(), is_staff=False, is_superadmin=False)
    mock_db.get.side_effect = lambda model, key: project if model is Project else owner
    monkeypatch.setattr(permissions, 'effective_project_role', lambda *a: ProjectRole.editor)
    monkeypatch.setattr(campaign.time, 'time', lambda: campaign.ENDS_AT_TIMESTAMP)
    from apps.api.services import whop_auth
    monkeypatch.setattr(whop_auth, 'require_customer_entitlement', MagicMock(side_effect=HTTPException(401)))
    with pytest.raises(HTTPException) as exc:
        permissions.require_project_role(mock_db, project.id, editor, ProjectRole.editor)
    assert exc.value.detail['code'] == 'campaign_expired'


def test_completed_guest_upload_acknowledged_after_cutoff(mock_db, monkeypatch):
    from apps.api.routers import requests
    from apps.api.models.asset import ProcessingStatus
    from fastapi import BackgroundTasks
    req = MagicMock(completed_at=None)
    version = MagicMock(processing_status=ProcessingStatus.processing)
    check = MagicMock()
    monkeypatch.setattr(requests, '_live_request', lambda db, token, **kwargs: req if kwargs.get('recovery') else (_ for _ in ()).throw(campaign.expired_error()))
    monkeypatch.setattr(requests, 'locked_request', lambda *a: req)
    monkeypatch.setattr(requests, '_owned_media', lambda *a: (MagicMock(), version))
    monkeypatch.setattr(requests, 'complete_multipart_upload', check)
    result = requests.guest_complete('token', requests.GuestComplete(s3_key='key', upload_id='upload', parts=[]), BackgroundTasks(), mock_db)
    assert result['status'] == 'processing'
    check.assert_not_called()


def test_usage_queries_project_owner_and_accepts_only_known_successful_bytes(mock_db, monkeypatch):
    from apps.api.services import campaign_usage
    user = customer()
    asset_id, version_id = uuid.uuid4(), uuid.uuid4()
    mock_db.join.return_value = mock_db
    mock_db.all.return_value = [(asset_id, version_id)]
    mock_db.count.return_value = 1
    monkeypatch.setattr(campaign_usage.review_bridge, 'asset_stats', lambda _: {
        str(asset_id): {'reviewed': True, 'version_id': str(version_id), 'openMustFix': 2},
        str(uuid.uuid4()): {'reviewed': True, 'version_id': str(version_id), 'openMustFix': 0}})
    record = MagicMock()
    monkeypatch.setattr(campaign_usage, 'record_successes', record)
    assert campaign_usage.refresh_usage(mock_db, user) == 1
    record.assert_called_once_with(mock_db, user, {str(asset_id)})
    filters = ' '.join(str(arg) for call in mock_db.filter.call_args_list for arg in call.args)
    assert 'projects.created_by' in filters
    assert 'upload_requests.created_by' not in filters


def test_usage_observation_keeps_callers_transaction_lock(mock_db):
    from apps.api.services.campaign_usage import record_successes
    record_successes(mock_db, customer(), {str(uuid.uuid4())})
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_not_called()


def test_november_revision_does_not_turn_failed_october_asset_into_campaign_usage(mock_db, monkeypatch):
    from apps.api.services import campaign_usage
    from apps.api.models.project import Project
    owner = customer(paid=True)
    project = Project(id=uuid.uuid4(), created_by=owner.id)
    asset_id, old_version, new_version = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    mock_db.get.side_effect = [project, owner]
    mock_db.join.return_value = mock_db
    mock_db.all.return_value = [(asset_id, old_version)]
    record = MagicMock()
    monkeypatch.setattr(campaign_usage, 'record_successes', record)
    campaign_usage.record_request_successes(mock_db, MagicMock(project_id=project.id), [
        {'asset_id': str(asset_id), 'version_id': str(new_version), 'review_state': 'clear'}])
    record.assert_called_once_with(mock_db, owner, set())
