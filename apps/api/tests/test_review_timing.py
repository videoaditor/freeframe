"""Private timing context is exact-version evidence, never guest metadata."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from apps.api.services.review_timing import private_timing_context


def test_guest_and_wrong_service_key_do_not_query_private_timing():
    db = MagicMock()
    with patch('apps.api.services.review_timing.settings') as settings:
        settings.service_api_key = 'real-service-key'
        settings.service_api_key_email = 'service@example.test'
        for key in (None, '', 'wrong'):
            for user in (None, SimpleNamespace(email='service@example.test')):
                assert private_timing_context(db, key, 'share', uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), service_user=user) == {}
    db.query.assert_not_called()


def test_context_uses_request_submission_of_exact_version_and_authoritative_project():
    db = MagicMock()
    asset, version, tenant = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    submitted = datetime(2026, 10, 7, tzinfo=timezone.utc)
    db.query.return_value.filter.return_value.first.side_effect = [
        SimpleNamespace(version_number=2), SimpleNamespace(submitted_at=submitted)]
    with patch('apps.api.services.review_timing.settings') as settings:
        settings.service_api_key = 'real-service-key'
        settings.service_api_key_email = 'service@example.test'
        result = private_timing_context(db, 'real-service-key', 'share', asset, version, tenant, service_user=SimpleNamespace(email='service@example.test'))
    assert result == {'timing_context': {'tenant_id': str(tenant), 'submitted_at': submitted.isoformat()}}
    sql = ' '.join(str(c) for call in db.query.return_value.filter.call_args_list for c in call.args)
    assert 'asset_versions.id' in sql and 'asset_versions.deleted_at IS NULL' in sql
    assert 'request_uploads.version_number' in sql and 'upload_requests.project_id' in sql
    assert 'upload_requests.revoked_at IS NULL' in sql


def test_missing_submission_is_not_invented():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with patch('apps.api.services.review_timing.settings') as settings:
        settings.service_api_key = 'key'
        settings.service_api_key_email = 'service@example.test'
        assert private_timing_context(db, 'key', 'share', uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), service_user=SimpleNamespace(email='service@example.test')) == {}


def test_elapsed_uses_committed_submission_even_while_reading():
    from apps.api.routers.requests import _review_assets
    from apps.api.models.asset import ProcessingStatus
    db = MagicMock()
    asset = SimpleNamespace(id=uuid.uuid4())
    version = SimpleNamespace(id=uuid.uuid4(), version_number=2, processing_status=ProcessingStatus.ready)
    submitted = datetime(2026, 10, 7, tzinfo=timezone.utc)
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [version]
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(submitted_at=submitted)
    req = SimpleNamespace(id=uuid.uuid4())
    with patch('apps.api.routers.requests._version_review', return_value={'review_progress': {'stage': 'reading'}, 'review_state': 'reviewing'}), patch('apps.api.services.campaign_usage.record_request_successes'), patch('apps.api.routers.requests.datetime') as clock:
        clock.now.return_value = datetime(2026, 10, 7, 0, 4, 1, tzinfo=timezone.utc)
        result = _review_assets(db, req, [asset], None, {})
    assert result[0]['review_progress']['elapsedSeconds'] == 241
    assert result[0]['review_progress']['queued_at'] == submitted.isoformat()


def test_matching_key_with_rejected_or_different_principal_cannot_read_private_context():
    db=MagicMock()
    with patch('apps.api.services.review_timing.settings') as settings:
        settings.service_api_key='key'; settings.service_api_key_email='service@example.test'
        for user in (None, SimpleNamespace(email='someone@example.test')):
            assert private_timing_context(db,'key','share',uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),service_user=user)=={}
    db.query.assert_not_called()
