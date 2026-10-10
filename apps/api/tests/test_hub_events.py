"""Outbound hub events: a guest comment on a hand-in version, and a version completed through the
hand-in lane. Modelled on test_folder_handins.py's direct service-level style for automation_share.
"""
import hashlib
import hmac
import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.api.config import settings


def _handin_request(card_url="https://trello.com/c/abc12345", folder_id=None, editor_email="editor@aditor.ai"):
    return SimpleNamespace(
        folder_id=folder_id or uuid.uuid4(),
        iteration_state={"internal_handin": {"card_url": card_url, "editor_name": "Editor"}},
        last_uploader_email=editor_email,
    )


def _db_with_request(req):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = req
    return db


def test_webhook_is_off_by_default():
    from apps.api.services import hub_events
    settings.hub_events_webhook_url = ""
    assert hub_events.is_enabled() is False
    hub_events.announce_client_comment(MagicMock(), MagicMock(), MagicMock(), "A Client")
    hub_events.announce_revision_submitted(MagicMock(), MagicMock(), uuid.uuid4())  # must not raise


def test_a_guest_comment_on_a_handin_version_posts_a_signed_client_comment_event(monkeypatch):
    from apps.api.services import hub_events
    settings.hub_events_webhook_url = "https://hub.aditor.ai/api/revision/freeframe-webhook"
    settings.hub_events_webhook_secret = "s3cret"
    try:
        folder_id = uuid.uuid4()
        req = _handin_request(folder_id=folder_id)
        db = _db_with_request(req)
        asset = SimpleNamespace(folder_id=folder_id)
        version_id = uuid.uuid4()
        comment = SimpleNamespace(id=uuid.uuid4(), body="Make the logo bigger", guest_author_id=uuid.uuid4(),
                                  visibility="public", version_id=version_id)

        sent = {}

        def fake_post(url, content=None, headers=None, timeout=None):
            sent["url"] = url
            sent["content"] = content
            sent["headers"] = headers
            return MagicMock(status_code=200)

        monkeypatch.setattr(hub_events.httpx, "post", fake_post)
        hub_events.announce_client_comment(db, comment, asset, "A Client")

        assert sent["url"] == "https://hub.aditor.ai/api/revision/freeframe-webhook"
        payload = json.loads(sent["content"])
        assert payload == {
            "event": "client_comment",
            "card_url": "https://trello.com/c/abc12345",
            "editor_email": "editor@aditor.ai",
            "comment": {"id": str(comment.id), "body": "Make the logo bigger", "author_name": "A Client"},
            "version_id": str(version_id),
        }
        expected_sig = hmac.new(b"s3cret", sent["content"], hashlib.sha256).hexdigest()
        assert sent["headers"]["X-Aditor-Signature"] == expected_sig
    finally:
        settings.hub_events_webhook_url = ""
        settings.hub_events_webhook_secret = ""


def test_an_internal_author_comment_emits_nothing(monkeypatch):
    """A team member's comment (`author_id` set, no `guest_author_id`) is never a client ask."""
    from apps.api.services import hub_events
    settings.hub_events_webhook_url = "https://example.invalid/hook"
    try:
        post = MagicMock()
        monkeypatch.setattr(hub_events.httpx, "post", post)
        comment = SimpleNamespace(id=uuid.uuid4(), body="Looks good", guest_author_id=None,
                                  visibility="public", version_id=uuid.uuid4())
        hub_events.announce_client_comment(MagicMock(), comment, MagicMock(), "A Teammate")
        post.assert_not_called()
    finally:
        settings.hub_events_webhook_url = ""


def test_an_auto_review_finding_emits_nothing(monkeypatch):
    """The craft reviewer's guest comments are stored visibility="internal" at write time
    (routers/comments.py `_guest_comment_visibility` / `publish_review_comment`) - never a client ask."""
    from apps.api.services import hub_events
    settings.hub_events_webhook_url = "https://example.invalid/hook"
    try:
        post = MagicMock()
        monkeypatch.setattr(hub_events.httpx, "post", post)
        comment = SimpleNamespace(id=uuid.uuid4(), body="Must fix - color is off", guest_author_id=uuid.uuid4(),
                                  visibility="internal", version_id=uuid.uuid4())
        hub_events.announce_client_comment(MagicMock(), comment, MagicMock(), "Auto Review")
        post.assert_not_called()
    finally:
        settings.hub_events_webhook_url = ""


def test_a_guest_comment_outside_any_handin_emits_nothing(monkeypatch):
    """A plain project/folder share comment with no hand-in request behind it is skipped, not errored."""
    from apps.api.services import hub_events
    settings.hub_events_webhook_url = "https://example.invalid/hook"
    try:
        post = MagicMock()
        monkeypatch.setattr(hub_events.httpx, "post", post)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None  # no UploadRequest for this folder
        asset = SimpleNamespace(folder_id=uuid.uuid4())
        comment = SimpleNamespace(id=uuid.uuid4(), body="Nice!", guest_author_id=uuid.uuid4(),
                                  visibility="public", version_id=uuid.uuid4())
        hub_events.announce_client_comment(db, comment, asset, "A Client")
        post.assert_not_called()
    finally:
        settings.hub_events_webhook_url = ""


def test_a_completed_handin_version_posts_a_signed_revision_submitted_event(monkeypatch):
    from apps.api.services import hub_events
    settings.hub_events_webhook_url = "https://hub.aditor.ai/api/revision/freeframe-webhook"
    settings.hub_events_webhook_secret = "s3cret"
    try:
        folder_id = uuid.uuid4()
        req = _handin_request(folder_id=folder_id)
        db = _db_with_request(req)
        asset = SimpleNamespace(folder_id=folder_id)
        version_id = uuid.uuid4()

        sent = {}
        monkeypatch.setattr(hub_events.httpx, "post",
                            lambda url, content=None, headers=None, timeout=None: sent.update(json.loads(content)) or MagicMock())
        hub_events.announce_revision_submitted(db, asset, version_id)

        assert sent == {
            "event": "revision_submitted",
            "card_url": "https://trello.com/c/abc12345",
            "editor_email": "editor@aditor.ai",
            "version_id": str(version_id),
        }
    finally:
        settings.hub_events_webhook_url = ""
        settings.hub_events_webhook_secret = ""


def test_a_version_outside_any_handin_emits_nothing(monkeypatch):
    from apps.api.services import hub_events
    settings.hub_events_webhook_url = "https://example.invalid/hook"
    try:
        post = MagicMock()
        monkeypatch.setattr(hub_events.httpx, "post", post)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        asset = SimpleNamespace(folder_id=None)  # a plain (non-request) upload has no folder here
        hub_events.announce_revision_submitted(db, asset, uuid.uuid4())
        post.assert_not_called()
    finally:
        settings.hub_events_webhook_url = ""


def test_a_failing_webhook_never_breaks_the_comment_or_upload(monkeypatch):
    from apps.api.services import hub_events
    settings.hub_events_webhook_url = "https://example.invalid/hook"
    try:
        def boom(*a, **k):
            raise RuntimeError("network down")
        monkeypatch.setattr(hub_events.httpx, "post", boom)
        folder_id = uuid.uuid4()
        db = _db_with_request(_handin_request(folder_id=folder_id))
        asset = SimpleNamespace(folder_id=folder_id)
        comment = SimpleNamespace(id=uuid.uuid4(), body="x", guest_author_id=uuid.uuid4(),
                                  visibility="public", version_id=uuid.uuid4())
        hub_events.announce_client_comment(db, comment, asset, "A Client")   # must not raise
        hub_events.announce_revision_submitted(db, asset, uuid.uuid4())      # must not raise
    finally:
        settings.hub_events_webhook_url = ""


def test_a_version_with_no_folder_emits_nothing():
    from apps.api.services import hub_events
    settings.hub_events_webhook_url = "https://example.invalid/hook"
    try:
        assert hub_events._handin_request_for_asset(MagicMock(), None) is None
        assert hub_events._handin_request_for_asset(MagicMock(), SimpleNamespace(folder_id=None)) is None
    finally:
        settings.hub_events_webhook_url = ""


def test_a_request_without_internal_handin_is_not_treated_as_one():
    """A regular (external editor) file request has no `internal_handin` key - never emits."""
    from apps.api.services import hub_events
    folder_id = uuid.uuid4()
    req = SimpleNamespace(folder_id=folder_id, iteration_state={"submitted": True}, last_uploader_email="x@y.com")
    db = _db_with_request(req)
    asset = SimpleNamespace(folder_id=folder_id)
    assert hub_events._handin_request_for_asset(db, asset) is None
