"""Product feedback persists independently of Slack; input is never executable."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError


@pytest.fixture(autouse=True)
def identity_override(client, test_user, request):
    # Existing authenticated fixture covers entitlement-gated routes; feedback
    # intentionally also accepts verified expired identities.
    from apps.api.main import app
    from apps.api.middleware.auth import get_identity_user
    if 'auth_headers' in request.fixturenames:
        app.dependency_overrides[get_identity_user] = lambda: test_user
    yield
    app.dependency_overrides.pop(get_identity_user, None)


def payload(**changes):
    return {"submission_id": str(uuid.uuid4()), "kind": "bug", "message": "Upload stalls", **changes}


def test_feedback_requires_authentication(client):
    assert client.post('/product-feedback', json=payload()).status_code == 401


@pytest.mark.parametrize('changes', [{"message": "  "}, {"message": "x" * 4001}, {"kind": "execute"}, {"author_id": str(uuid.uuid4())}, {"campaign_id": "spoofed"}])
def test_feedback_validates_input(client, auth_headers, changes):
    assert client.post('/product-feedback', headers=auth_headers, json=payload(**changes)).status_code == 422


def test_feedback_persists_trusted_author_and_campaign(client, auth_headers, test_user, mock_db):
    test_user.suite_account_id = 'account-1'
    test_user.suite_campaign = {"id": "telehealth_october_2026"}
    response = client.post('/product-feedback', headers=auth_headers, json=payload(page_path='/requests/secret?token=private#secret'))
    assert response.status_code == 201
    assert response.json()['status'] == 'received'
    row = mock_db.add.call_args.args[0]
    assert row.author_id == test_user.id
    assert row.suite_account_id == 'account-1'
    assert row.campaign_id == 'telehealth_october_2026'
    assert row.page_path == '/requests'
    mock_db.commit.assert_called_once()


def test_feedback_repeated_submission_returns_original_receipt(client, auth_headers, mock_db):
    existing = SimpleNamespace(id=uuid.uuid4())
    mock_db.first.return_value = existing
    response = client.post('/product-feedback', headers=auth_headers, json=payload())
    assert response.json()['id'] == str(existing.id)
    mock_db.add.assert_not_called()
    query = str(mock_db.filter.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    assert 'author_id' in query


def test_feedback_concurrent_duplicate_returns_committed_receipt(client, auth_headers, mock_db):
    existing = SimpleNamespace(id=uuid.uuid4())
    mock_db.first.side_effect = [None, existing]
    mock_db.commit.side_effect = IntegrityError('insert', {}, Exception())
    response = client.post('/product-feedback', headers=auth_headers, json=payload())
    assert response.json()['id'] == str(existing.id)
    mock_db.rollback.assert_called_once()


def test_failed_storage_never_returns_receipt(client, auth_headers, mock_db):
    mock_db.commit.side_effect = RuntimeError('db unavailable')
    assert client.post('/product-feedback', headers=auth_headers, json=payload()).status_code == 500


def test_feedback_queue_denies_customers(client, auth_headers, test_user):
    test_user.is_staff = False
    assert client.get('/product-feedback', headers=auth_headers).status_code == 403


def test_feedback_queue_pagination(client, auth_headers, test_user, mock_db):
    test_user.is_staff = True
    mock_db.order_by.return_value = mock_db
    mock_db.limit.return_value = mock_db
    mock_db.offset.return_value = mock_db
    response = client.get('/product-feedback?offset=25&limit=25', headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_offset": None}
    mock_db.offset.assert_called_once_with(25)
    assert client.get('/product-feedback?limit=101', headers=auth_headers).status_code == 422


def batch(status='pending'):
    return SimpleNamespace(id=uuid.uuid4(), status=status, text='Daily feedback', channel_id='C07UL6BAG1Z', created_at=datetime.now(timezone.utc), delivered_at=None, slack_ts=None, last_error=None)


def test_empty_digest_stays_silent():
    from apps.api.services.product_feedback import deliver_batch
    db, slack = MagicMock(), MagicMock()
    assert deliver_batch(db, None, slack) == 'empty'
    slack.post.assert_not_called()


def test_slack_failure_keeps_durable_batch_pending():
    from apps.api.services.product_feedback import deliver_batch, SlackRejected
    db, slack, pending = MagicMock(), MagicMock(), batch()
    slack.post.side_effect = SlackRejected('ratelimited')
    with pytest.raises(SlackRejected):
        deliver_batch(db, pending, slack)
    assert pending.status == 'pending'
    assert pending.delivered_at is None
    assert pending.last_error == 'ratelimited'


def test_timeout_does_not_blindly_repeat_send():
    from apps.api.services.product_feedback import deliver_batch, DeliveryUncertain
    db, slack, pending = MagicMock(), MagicMock(), batch()
    slack.post.side_effect = TimeoutError()
    with pytest.raises(DeliveryUncertain):
        deliver_batch(db, pending, slack)
    assert pending.status == 'sending'
    slack.find.return_value = None
    with pytest.raises(DeliveryUncertain):
        deliver_batch(db, pending, slack)
    slack.post.assert_called_once()


def test_retry_reconciles_slack_receipt_after_timeout():
    from apps.api.services.product_feedback import deliver_batch
    db, slack, pending = MagicMock(), MagicMock(), batch('sending')
    slack.find.return_value = '123.456'
    assert deliver_batch(db, pending, slack) == 'delivered'
    assert pending.slack_ts == '123.456'
    assert pending.delivered_at is not None
    slack.post.assert_not_called()


def test_successful_slack_send_checkpoints_only_after_confirmation():
    from apps.api.services.product_feedback import deliver_batch
    db, slack, pending = MagicMock(), MagicMock(), batch()
    def post(value):
        assert value.status == 'sending'
        assert value.delivered_at is None
        assert db.commit.call_count == 1
        return '123.456'
    slack.post.side_effect = post
    assert deliver_batch(db, pending, slack) == 'delivered'
    assert pending.status == 'delivered'
    assert db.commit.call_count == 2


def test_digest_sanitizes_untrusted_text_and_caps_output():
    from apps.api.services.product_feedback import format_digest
    rows = [SimpleNamespace(kind='bug', message='<@U123> secret token=abc123 https://example.com?token=secret', campaign_id='telehealth_october_2026', tool='autoreview') for _ in range(500)]
    text = format_digest(rows, 'https://review.example.com')
    assert '<@U123>' not in text
    assert 'token=secret' not in text
    assert 'abc123' not in text
    assert len(text) < 30000
    assert '500' in text
    assert 'https://review.example.com/feedback' in text


def test_another_worker_holds_digest_lock_so_no_post_occurs(monkeypatch):
    from apps.api.tasks import product_feedback_tasks as task
    monkeypatch.setattr(task.settings, 'product_feedback_slack_token', 'test-token')
    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = False
    with patch.object(task.engine, 'connect') as connect, patch.object(task, 'deliver_batch') as deliver:
        connect.return_value.__enter__.return_value = connection
        assert task.run_feedback_digest() == 'busy'
        deliver.assert_not_called()


def test_missing_slack_configuration_does_not_touch_database(monkeypatch):
    from apps.api.tasks import product_feedback_tasks as task
    monkeypatch.setattr(task.settings, 'product_feedback_slack_token', '')
    with patch.object(task.engine, 'connect') as connect:
        assert task.run_feedback_digest() == 'unconfigured'
        connect.assert_not_called()


def test_preparing_batch_keeps_every_report_and_durable_membership():
    from apps.api.services.product_feedback import prepare_batch
    db = MagicMock()
    db.query.return_value = db
    db.filter.return_value = db
    db.order_by.return_value = db
    db.first.side_effect = [None, None, None]
    rows = [SimpleNamespace(id=uuid.uuid4(), kind='bug', message='Upload issue', tool='autoreview', campaign_id=None, digest_id=None) for _ in range(45)]
    db.all.return_value = rows
    prepared = prepare_batch(db, datetime.now(timezone.utc), 'C07UL6BAG1Z', 'https://review.example.com')
    assert all(row.digest_id == prepared.id for row in rows)
    assert '45 new reports' in prepared.text
    assert '5 additional reports' in prepared.text
    db.commit.assert_called_once()


def test_already_delivered_today_stops_second_daily_digest():
    from apps.api.services.product_feedback import prepare_batch
    db = MagicMock()
    db.query.return_value = db
    db.filter.return_value = db
    db.first.return_value = batch('delivered')
    assert prepare_batch(db, datetime.now(timezone.utc), 'channel', 'https://review.example.com') is None
    db.add.assert_not_called()


def test_slack_transport_uses_literal_text_and_durable_batch_metadata():
    from apps.api.services.product_feedback import SlackFeedbackClient
    value = batch()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {'ok': True, 'ts': '1.2'}
    with patch('apps.api.services.product_feedback.httpx.post', return_value=response) as post:
        assert SlackFeedbackClient('test').post(value) == '1.2'
    body = post.call_args.kwargs['json']
    assert body['metadata']['event_payload']['batch_id'] == str(value.id)
    assert body['mrkdwn'] is False
    assert body['unfurl_links'] is False


def test_daily_schedule_defaults_to_midnight_utc():
    from apps.api.tasks.celery_app import celery_app
    schedule = celery_app.conf.beat_schedule['daily-product-feedback']['schedule']
    assert schedule.hour == {0}
    assert schedule.minute == {0}
    assert celery_app.conf.timezone == 'UTC'
