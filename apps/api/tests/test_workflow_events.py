"""Outbound editor-workflow events to the company-DB store (app.log_workflow_event): a request-lane
hand-in, its finish, a revision response, and a resubmitted version all join the cross-tool journey.
Service-level, mock-driven, in the style of test_hub_events.py for its sibling hub_events.py.
"""
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.api.config import settings

FRONTEND = "https://feedback.aditor.ai"


def _req(**overrides):
    base = dict(
        id=uuid.uuid4(),
        token="tok_abc123",
        brand_slug="cust-0000000000000000",
        last_uploader_email="editor@aditor.ai",
        iteration_state={},
        completed_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _db_no_request_upload():
    """A db whose RequestUpload lookup always misses, so occurred_at falls back to "now"."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def _enable():
    settings.companydb_url = "https://db.aditor.ai"
    settings.companydb_workflow_jwt = "jwt-token"
    settings.frontend_url = FRONTEND


def _disable():
    settings.companydb_url = "https://db.aditor.ai"
    settings.companydb_workflow_jwt = ""


def test_emission_is_a_no_op_when_the_token_is_unset():
    from apps.api.services import workflow_events
    _disable()
    assert workflow_events.is_enabled() is False
    db = MagicMock()
    req = _req()
    asset = SimpleNamespace(id=uuid.uuid4(), folder_id=uuid.uuid4())
    version = SimpleNamespace(id=uuid.uuid4(), version_number=1)
    # None of these may raise, and none may post anything.
    workflow_events.announce_handin_uploaded(db, req, asset, version)
    workflow_events.announce_handin_finished(db, req)
    workflow_events.announce_revision_responded(db, req, asset, "c1")


def test_a_request_lane_handin_posts_a_bearer_authenticated_handin_uploaded_event(monkeypatch):
    from apps.api.services import workflow_events
    _enable()
    try:
        db = _db_no_request_upload()
        req = _req(brand_slug="brand-x", last_uploader_email="editor@aditor.ai")
        asset = SimpleNamespace(id=uuid.uuid4(), folder_id=uuid.uuid4())
        version = SimpleNamespace(id=uuid.uuid4(), version_number=1)

        sent = {}

        def fake_post(url, content=None, headers=None, timeout=None):
            sent["url"] = url
            sent["content"] = content
            sent["headers"] = headers
            return MagicMock(status_code=200)

        monkeypatch.setattr(workflow_events.httpx, "post", fake_post)
        workflow_events.announce_handin_uploaded(db, req, asset, version)

        assert sent["url"] == "https://db.aditor.ai/rpc/log_workflow_event"
        assert sent["headers"]["Authorization"] == "Bearer jwt-token"
        payload = json.loads(sent["content"])
        assert payload["event"] == "handin.uploaded"
        assert payload["tool"] == "freeframe"
        assert payload["brand_slug"] == "brand-x"
        assert payload["email"] == "editor@aditor.ai"
        assert payload["person_id"] is None
        assert payload["card_ref"] == f"{FRONTEND}/r/tok_abc123"
        assert payload["props"] == {"version_no": 1, "version_id": str(version.id)}
        # Occurred-at falls back to "now" (ISO 8601, parseable) when no RequestUpload row exists.
        datetime.fromisoformat(payload["occurred_at"])
    finally:
        _disable()


def test_an_internal_handin_card_is_used_as_card_ref_over_the_review_link(monkeypatch):
    from apps.api.services import workflow_events
    _enable()
    try:
        db = _db_no_request_upload()
        card = "https://trello.com/c/AbCd1234"
        req = _req(iteration_state={"internal_handin": {"card_url": card}})
        asset = SimpleNamespace(id=uuid.uuid4(), folder_id=uuid.uuid4())
        version = SimpleNamespace(id=uuid.uuid4(), version_number=1)

        sent = {}
        monkeypatch.setattr(workflow_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: sent.update(json.loads(content)) or MagicMock())
        workflow_events.announce_handin_uploaded(db, req, asset, version)

        assert sent["card_ref"] == card
    finally:
        _disable()


def test_a_resubmitted_version_also_emits_version_resubmitted(monkeypatch):
    from apps.api.services import workflow_events
    _enable()
    try:
        db = _db_no_request_upload()
        req = _req()
        asset = SimpleNamespace(id=uuid.uuid4(), folder_id=uuid.uuid4())
        version = SimpleNamespace(id=uuid.uuid4(), version_number=2)

        events = []
        monkeypatch.setattr(workflow_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: events.append(json.loads(content)) or MagicMock())
        workflow_events.announce_handin_uploaded(db, req, asset, version)

        assert [e["event"] for e in events] == ["handin.uploaded", "version.resubmitted"]
        assert all(e["props"] == {"version_no": 2, "version_id": str(version.id)} for e in events)
    finally:
        _disable()


def test_the_first_version_never_emits_version_resubmitted(monkeypatch):
    from apps.api.services import workflow_events
    _enable()
    try:
        db = _db_no_request_upload()
        req = _req()
        asset = SimpleNamespace(id=uuid.uuid4(), folder_id=uuid.uuid4())
        version = SimpleNamespace(id=uuid.uuid4(), version_number=1)

        events = []
        monkeypatch.setattr(workflow_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: events.append(json.loads(content)) or MagicMock())
        workflow_events.announce_handin_uploaded(db, req, asset, version)

        assert [e["event"] for e in events] == ["handin.uploaded"]
    finally:
        _disable()


def test_a_plain_upload_with_no_linked_request_emits_nothing(monkeypatch):
    """The /upload/complete lane with no staff hand-in folder behind it has no request, so no
    card/brand can be resolved - stay silent rather than invent one."""
    from apps.api.services import workflow_events
    from apps.api.services import hub_events
    _enable()
    try:
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None  # no UploadRequest
        asset = SimpleNamespace(id=uuid.uuid4(), folder_id=uuid.uuid4())
        version = SimpleNamespace(id=uuid.uuid4(), version_number=1)

        post = MagicMock()
        monkeypatch.setattr(workflow_events.httpx, "post", post)
        assert hub_events._handin_request_for_asset(db, asset) is None
        workflow_events.announce_handin_uploaded(db, None, asset, version)
        post.assert_not_called()
    finally:
        _disable()


def test_a_plain_upload_resolves_its_linked_staff_handin_request(monkeypatch):
    """The /upload/complete lane DOES find a request when the asset's folder was converted into a
    staff internal hand-in (routers/requests.py folder_editor_request)."""
    from apps.api.services import workflow_events
    _enable()
    try:
        folder_id = uuid.uuid4()
        req = _req(folder_id=folder_id, iteration_state={"internal_handin": {"card_url": "https://trello.com/c/AbCd1234"}})
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [req, None]
        asset = SimpleNamespace(id=uuid.uuid4(), folder_id=folder_id)
        version = SimpleNamespace(id=uuid.uuid4(), version_number=1)

        sent = {}
        monkeypatch.setattr(workflow_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: sent.update(json.loads(content)) or MagicMock())
        workflow_events.announce_handin_uploaded(db, None, asset, version)

        assert sent["event"] == "handin.uploaded"
        assert sent["card_ref"] == "https://trello.com/c/AbCd1234"
    finally:
        _disable()


def test_occurred_at_prefers_the_request_uploads_submitted_at(monkeypatch):
    from apps.api.services import workflow_events
    _enable()
    try:
        submitted_at = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
        record = SimpleNamespace(submitted_at=submitted_at)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = record
        req = _req()
        asset = SimpleNamespace(id=uuid.uuid4(), folder_id=uuid.uuid4())
        version = SimpleNamespace(id=uuid.uuid4(), version_number=1)

        sent = {}
        monkeypatch.setattr(workflow_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: sent.update(json.loads(content)) or MagicMock())
        workflow_events.announce_handin_uploaded(db, req, asset, version)

        assert sent["occurred_at"] == submitted_at.isoformat()
    finally:
        _disable()


def test_handin_finished_posts_with_the_requests_completed_at(monkeypatch):
    from apps.api.services import workflow_events
    _enable()
    try:
        completed_at = datetime(2026, 10, 20, 9, 30, 0, tzinfo=timezone.utc)
        req = _req(brand_slug="brand-y", completed_at=completed_at)

        sent = {}
        monkeypatch.setattr(workflow_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: sent.update(json.loads(content)) or MagicMock())
        workflow_events.announce_handin_finished(MagicMock(), req)

        assert sent["event"] == "handin.finished"
        assert sent["brand_slug"] == "brand-y"
        assert sent["occurred_at"] == completed_at.isoformat()
        assert sent["props"] == {}
    finally:
        _disable()


def test_revision_responded_posts_with_the_asset_and_comment_id(monkeypatch):
    from apps.api.services import workflow_events
    _enable()
    try:
        req = _req()
        asset = SimpleNamespace(id=uuid.uuid4())

        sent = {}
        monkeypatch.setattr(workflow_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: sent.update(json.loads(content)) or MagicMock())
        workflow_events.announce_revision_responded(MagicMock(), req, asset, "c-123")

        assert sent["event"] == "revision.responded"
        assert sent["props"] == {"asset_id": str(asset.id), "comment_id": "c-123"}
    finally:
        _disable()


def test_a_request_with_no_resolved_editor_emits_nothing(monkeypatch):
    """No last_uploader_email yet (identity arrives only at completion) -> stay silent."""
    from apps.api.services import workflow_events
    _enable()
    try:
        req = _req(last_uploader_email=None)
        post = MagicMock()
        monkeypatch.setattr(workflow_events.httpx, "post", post)
        workflow_events.announce_handin_finished(MagicMock(), req)
        post.assert_not_called()
    finally:
        _disable()


def test_a_failing_rpc_never_breaks_the_request_it_reports(monkeypatch):
    from apps.api.services import workflow_events
    _enable()
    try:
        def boom(*a, **k):
            raise RuntimeError("company DB unreachable")
        monkeypatch.setattr(workflow_events.httpx, "post", boom)
        req = _req()
        asset = SimpleNamespace(id=uuid.uuid4(), folder_id=uuid.uuid4())
        version = SimpleNamespace(id=uuid.uuid4(), version_number=1)
        db = _db_no_request_upload()
        workflow_events.announce_handin_uploaded(db, req, asset, version)  # must not raise
        workflow_events.announce_handin_finished(MagicMock(), req)  # must not raise
        workflow_events.announce_revision_responded(MagicMock(), req, asset, "c1")  # must not raise
    finally:
        _disable()
