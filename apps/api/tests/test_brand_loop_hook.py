"""Brand Loop F2: every committed comment on a brand-linked project is sent to AutoReview, after the
response, best effort. Contract: feedback-agent docs/superpowers/specs/2026-10-16-brand-loop-CONTRACT.md.
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from apps.api.config import settings
from apps.api.services import brand_loop


@pytest.fixture
def enabled():
    settings.autoreview_url, settings.brand_loop_secret = "https://review.aditor.ai/", "s3cret"
    yield
    settings.autoreview_url, settings.brand_loop_secret = "", ""


def _db(slug):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(autoreview_brand_slug=slug)
    return db


def _comment(**kw):
    values = dict(id=uuid.uuid4(), parent_id=None, timecode_start=12.4, body="Logo zu klein",
                  created_at=datetime(2026, 10, 16, 9, 30, tzinfo=timezone.utc), visibility="public")
    values.update(kw)
    return SimpleNamespace(**values)


def _asset():
    return SimpleNamespace(id=uuid.uuid4(), project_id=uuid.uuid4())


def test_queues_contract_payload(enabled):
    tasks, comment, asset = BackgroundTasks(), _comment(), _asset()
    brand_loop.queue_comment(tasks, _db("audibene-gmbh"), comment, asset,
                             author_email="kunde@audibene.de", share_token="tok")
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].args[0] == {
        "v": 1, "commentId": str(comment.id), "brandSlug": "audibene-gmbh", "assetId": str(asset.id),
        "shareToken": "tok", "timecode": 12.4, "body": "Logo zu klein", "authorEmail": "kunde@audibene.de",
        "createdAt": "2026-10-16T09:30:00+00:00",
    }


def test_disabled_without_env():
    tasks, db = BackgroundTasks(), _db("audibene-gmbh")
    brand_loop.queue_comment(tasks, db, _comment(), _asset(), author_email="a@b.de")
    assert tasks.tasks == []
    db.query.assert_not_called()


def test_skips_project_without_slug(enabled):
    tasks = BackgroundTasks()
    brand_loop.queue_comment(tasks, _db(None), _comment(), _asset(), author_email="a@b.de")
    assert tasks.tasks == []


def test_skips_non_public_comments(enabled):
    """Internal staff notes and the automation reviewer's (internal) findings never leave FreeFrame."""
    tasks = BackgroundTasks()
    brand_loop.queue_comment(tasks, _db("audibene-gmbh"), _comment(visibility="internal"), _asset(),
                             author_email="editor@aditor.ai")
    assert tasks.tasks == []


def test_null_timecode_is_sent_as_null(enabled):
    tasks = BackgroundTasks()
    brand_loop.queue_comment(tasks, _db("audibene-gmbh"), _comment(timecode_start=None), _asset(),
                             author_email="a@b.de")
    assert tasks.tasks[0].args[0]["timecode"] is None


def test_lookup_failure_never_raises(enabled):
    db = MagicMock()
    db.query.side_effect = RuntimeError("db gone")
    tasks = BackgroundTasks()
    brand_loop.queue_comment(tasks, db, _comment(), _asset(), author_email="a@b.de")
    assert tasks.tasks == []


def test_post_uses_bearer_and_3s_timeout(enabled, monkeypatch):
    calls = []
    monkeypatch.setattr(brand_loop.httpx, "post", lambda url, **kw: calls.append((url, kw)) or MagicMock(status_code=202))
    brand_loop.post_comment({"v": 1, "authorEmail": "kunde@audibene.de"})
    assert calls == [("https://review.aditor.ai/api/brand-loop/comment",
                      {"json": {"v": 1, "authorEmail": "kunde@audibene.de", "authorIsClient": True},
                       "headers": {"authorization": "Bearer s3cret"}, "timeout": 3})]


def test_post_swallows_errors(enabled, monkeypatch):
    def boom(*a, **k):
        raise TimeoutError
    monkeypatch.setattr(brand_loop.httpx, "post", boom)
    brand_loop.post_comment({"v": 1})


# ── Call sites ────────────────────────────────────────────────────────────────

def _member(is_staff):
    return SimpleNamespace(id=uuid.uuid4(), email="m@x.de", name="M", is_staff=is_staff, is_superadmin=False)


@pytest.mark.parametrize("is_staff", [True, False])
def test_create_comment_queues_hook(is_staff):
    import apps.api.routers.comments as c
    asset, user, tasks = _asset(), _member(is_staff), BackgroundTasks()
    asset.created_by = user.id
    db = MagicMock()
    body = c.CommentCreate(version_id=uuid.uuid4(), body="Musik leiser")
    with patch.object(c, "_get_asset", return_value=asset), patch.object(c, "require_asset_access"), \
         patch.object(c, "_create_mentions"), patch.object(c, "_build_comment_response"), \
         patch.object(c.brand_loop, "queue_comment") as queue:
        c.create_comment(asset.id, body, db, user, background_tasks=tasks)
    _, _, comment, got_asset = queue.call_args.args
    assert queue.call_args.args[0] is tasks and got_asset is asset and comment.body == "Musik leiser"
    assert queue.call_args.kwargs == {"author_email": "m@x.de"}


def test_reply_queues_hook():
    import apps.api.routers.comments as c
    asset, user, tasks = _asset(), _member(True), BackgroundTasks()
    parent = SimpleNamespace(id=uuid.uuid4(), version_id=uuid.uuid4(), author_id=user.id)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = parent
    with patch.object(c, "_get_asset", return_value=asset), patch.object(c, "require_asset_access"), \
         patch.object(c, "_create_mentions"), patch.object(c, "_build_comment_response"), \
         patch.object(c.brand_loop, "queue_comment") as queue:
        c.reply_to_comment(asset.id, parent.id, c.CommentCreate(version_id=parent.version_id, body="ok"), db, user,
                           background_tasks=tasks)
    assert queue.call_args.args[2].parent_id == parent.id
    assert queue.call_args.kwargs == {"author_email": "m@x.de"}


def test_guest_share_comment_queues_hook_as_client():
    import apps.api.routers.comments as c
    from apps.api.models.share import SharePermission
    asset, tasks = _asset(), BackgroundTasks()
    asset.name = "Hook v3"
    link = SimpleNamespace(id=uuid.uuid4(), asset_id=asset.id, permission=SharePermission.comment)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=uuid.uuid4())
    body = c.GuestCommentCreate(body="Bitte Untertitel größer", version_id=uuid.uuid4(),
                                guest_email="Kunde@Audibene.de", guest_name="Kunde")
    with patch.object(c, "validate_share_link_with_session", return_value=link), \
         patch.object(c, "_get_asset", return_value=asset), patch.object(c, "validate_asset_in_share"), \
         patch.object(c, "validate_comment_version"), patch.object(c, "_build_comment_response"), \
         patch("apps.api.services.hub_events.announce_client_comment"), \
         patch.object(c.brand_loop, "queue_comment") as queue:
        c.guest_comment("tok", body, None, db, None, None, background_tasks=tasks)
    assert queue.call_args.kwargs == {"author_email": "kunde@audibene.de", "share_token": "tok"}


def test_http_route_injects_background_tasks(client, auth_headers, mock_db, test_user):
    """FastAPI must inject BackgroundTasks despite the None default (kept for direct callers)."""
    import apps.api.routers.comments as c
    test_user.is_staff = True
    asset = _asset()
    asset.created_by = test_user.id
    with patch.object(c, "_get_asset", return_value=asset), patch.object(c, "require_asset_access"), \
         patch.object(c, "_create_mentions"), \
         patch.object(c, "_build_comment_response", return_value={}), \
         patch.object(c.brand_loop, "queue_comment") as queue:
        mock_db.first.return_value = SimpleNamespace(id=uuid.uuid4())
        client.post(f"/assets/{uuid.uuid4()}/comments", json={"version_id": str(uuid.uuid4()), "body": "x"}, headers=auth_headers)
    assert isinstance(queue.call_args.args[0], BackgroundTasks)


def test_signed_in_staff_on_a_share_link_is_not_a_client():
    import apps.api.routers.comments as c
    from apps.api.models.share import SharePermission
    asset, tasks, user = _asset(), BackgroundTasks(), _member(True)
    asset.name = "Hook v3"
    link = SimpleNamespace(id=uuid.uuid4(), asset_id=asset.id, permission=SharePermission.comment)
    db = MagicMock()
    with patch.object(c, "validate_share_link_with_session", return_value=link), \
         patch.object(c, "_get_asset", return_value=asset), patch.object(c, "validate_asset_in_share"), \
         patch.object(c, "validate_comment_version"), patch.object(c, "_build_comment_response"), \
         patch("apps.api.services.hub_events.announce_client_comment"), \
         patch.object(c.brand_loop, "queue_comment") as queue:
        c.guest_comment("tok", c.GuestCommentCreate(body="intern", version_id=uuid.uuid4()), None, db, user, None,
                        background_tasks=tasks)
    assert queue.call_args.kwargs == {"author_email": "m@x.de", "share_token": "tok"}


def test_hook_is_queued_even_when_the_hub_call_raises(enabled):
    import apps.api.routers.comments as c
    from apps.api.models.share import SharePermission
    asset, tasks = _asset(), BackgroundTasks()
    asset.name = "Hook v3"
    link = SimpleNamespace(id=uuid.uuid4(), asset_id=asset.id, permission=SharePermission.comment)
    db = MagicMock()
    body = c.GuestCommentCreate(body="x", version_id=uuid.uuid4(), guest_email="k@a.de", guest_name="K")
    with patch.object(c, "validate_share_link_with_session", return_value=link), \
         patch.object(c, "_get_asset", return_value=asset), patch.object(c, "validate_asset_in_share"), \
         patch.object(c, "validate_comment_version"), \
         patch("apps.api.services.hub_events.announce_client_comment", side_effect=RuntimeError("hub")), \
         patch.object(c.brand_loop, "queue_comment") as queue:
        with pytest.raises(RuntimeError):
            c.guest_comment("tok", body, None, db, None, None, background_tasks=tasks)
    queue.assert_called_once()


# ── authorIsClient: Aditor staff by email domain or people directory, never User.is_staff ─────

@pytest.mark.parametrize("email,client", [
    ("kunde@audibene.de", True),     # invited client account (is_staff defaults to true) is a client
    ("Alan@Aditor.ai", False),
    ("", True),
])
def test_author_is_client_by_domain(email, client, monkeypatch):
    monkeypatch.setattr(settings, "directory_lookup_url", None)
    assert brand_loop.is_aditor_staff(email) is (not client)


def test_directory_listed_editor_is_staff(monkeypatch):
    from apps.api.services import directory_service
    monkeypatch.setattr(settings, "directory_lookup_url", "https://dir/{email}")
    monkeypatch.setattr(directory_service, "find_person", lambda e: {"status": "active"} if e == "ed@gmail.com" else None)
    assert brand_loop.is_aditor_staff("ed@gmail.com") is True
    assert brand_loop.is_aditor_staff("kunde@audibene.de") is False


def test_directory_down_falls_back_to_domain(monkeypatch):
    from apps.api.services import directory_service
    def down(e):
        raise directory_service.DirectoryUnavailable("x")
    monkeypatch.setattr(settings, "directory_lookup_url", "https://dir/{email}")
    monkeypatch.setattr(directory_service, "find_person", down)
    assert brand_loop.is_aditor_staff("ed@gmail.com") is False


def test_invited_client_account_is_sent_as_client(enabled, monkeypatch):
    """End to end through the router: an invited @audibene.de account with is_staff=True."""
    import apps.api.routers.comments as c
    monkeypatch.setattr(settings, "directory_lookup_url", None)
    asset, tasks = _asset(), BackgroundTasks()
    user = SimpleNamespace(id=uuid.uuid4(), email="pruefer@audibene.de", name="P", is_staff=True, is_superadmin=False)
    asset.created_by = user.id
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(autoreview_brand_slug="audibene-gmbh")
    sent = []
    monkeypatch.setattr(brand_loop.httpx, "post", lambda url, **kw: sent.append(kw["json"]) or MagicMock(status_code=202))
    with patch.object(c, "_get_asset", return_value=asset), patch.object(c, "require_asset_access"), \
         patch.object(c, "_create_mentions"), patch.object(c, "_build_comment_response"), \
         patch.object(db, "refresh", side_effect=lambda o: setattr(o, "created_at", datetime(2026, 10, 16, tzinfo=timezone.utc))):
        c.create_comment(asset.id, c.CommentCreate(version_id=uuid.uuid4(), body="Logo größer"), db, user, background_tasks=tasks)
    for task in tasks.tasks:
        task.func(*task.args, **task.kwargs)
    assert sent and sent[0]["authorIsClient"] is True and sent[0]["authorEmail"] == "pruefer@audibene.de"
