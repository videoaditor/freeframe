"""Comment history for the Brand Loop backfill: bridge-only, public comments, backfill row shape."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from apps.api.config import settings
from apps.api.services import comment_history

URL = "/internal/review/comments-export"


def _comment(**kw):
    base = dict(id=uuid.uuid4(), body="Logo zu klein", timecode_start=3.5, resolved=True, parent_id=None,
                review_source=None, created_at=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc))
    return SimpleNamespace(**{**base, **kw})


def _project(**kw):
    base = dict(id=uuid.uuid4(), name="Audibene Workspace", autoreview_brand_slug=None, review_brand_binding=None)
    return SimpleNamespace(**{**base, **kw})


ASSET = SimpleNamespace(id=uuid.uuid4(), name="Hook1.mp4")


def test_row_has_the_backfill_shape_and_ids():
    c = _comment()
    p = _project(autoreview_brand_slug="audibene-gmbh")
    row = comment_history.export_row(c, ASSET, p, 2, "Kunde@Audibene.de", staff=False)
    assert row["id"] == str(c.id) and row["asset_id"] == str(ASSET.id) and row["version"] == 2
    assert (row["brand"], row["brand_slug"], row["label"]) == ("Audibene Workspace", "audibene-gmbh", "Hook1.mp4")
    assert (row["text"], row["tc"], row["resolved"], row["parent"]) == ("Logo zu klein", 3.5, True, None)
    assert row["at"] == "2026-10-01T09:00:00+00:00"
    assert (row["email_dom"], row["client"], row["bot"]) == ("audibene.de", True, False)
    assert "Kunde" not in str(row)  # the address itself never leaves FreeFrame, only its domain


def test_reviewer_comments_are_bot_and_staff_is_not_client():
    row = comment_history.export_row(_comment(review_source={"requirement_id": "r1"}), ASSET, _project(), 1,
                                     "editor@aditor.ai", staff=True)
    assert row["bot"] is True and row["client"] is False and row["email_dom"] == "aditor.ai"


def test_brand_slug_falls_back_to_the_confirmed_review_brand_never_the_name():
    assert comment_history.brand_slug_of(_project(review_brand_binding={"brand_slug": "glow25"})) == "glow25"
    assert comment_history.brand_slug_of(_project(autoreview_brand_slug="a", review_brand_binding={"brand_slug": "b"})) == "a"
    assert comment_history.brand_slug_of(_project()) is None


def test_endpoint_needs_the_bridge_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "review_bridge_secret", "s3cret")
    assert client.get(URL).status_code in (401, 403)
    assert client.get(URL, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_endpoint_pages_with_a_cursor(client, monkeypatch):
    monkeypatch.setattr(settings, "review_bridge_secret", "s3cret")
    seen = {}

    def fake(db, **kw):
        seen.update(kw)
        return {"items": [], "next": None}

    monkeypatch.setattr("apps.api.routers.comment_history.export_comments", fake)
    after_id = uuid.uuid4()
    r = client.get(URL, params={"after": "2026-10-01T09:00:00+00:00", "after_id": str(after_id), "limit": 50},
                   headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200 and r.json() == {"items": [], "next": None}
    assert r.headers["cache-control"] == "private, no-store"
    assert seen["limit"] == 50 and seen["after_id"] == after_id and seen["after"].year == 2026
    assert client.get(URL, params={"limit": 5000}, headers={"Authorization": "Bearer s3cret"}).status_code == 422
