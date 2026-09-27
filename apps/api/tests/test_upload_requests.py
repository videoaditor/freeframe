"""Platform v2: file requests, customer accounts, and the review bridge.

Spec: docs/superpowers/specs/2026-09-28-review-platform-v2-design.md.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from apps.api.models.project import ProjectRole


def _req(**over):
    from apps.api.models.upload_request import UploadRequest
    r = UploadRequest(token="t", project_id=uuid.uuid4(), folder_id=uuid.uuid4(), created_by=uuid.uuid4(),
                      title="UraVia 48", review_share_token="s")
    r.revoked_at = None
    r.expires_at = None
    for k, v in over.items():
        setattr(r, k, v)
    return r


# ── The link's own state ──────────────────────────────────────────────────────

def test_a_fresh_request_is_live():
    from apps.api.routers.requests import request_state
    assert request_state(_req(), datetime.now(timezone.utc)) == "live"


def test_an_expired_request_is_closed():
    from apps.api.routers.requests import request_state
    now = datetime.now(timezone.utc)
    assert request_state(_req(expires_at=now - timedelta(seconds=1)), now) == "expired"
    assert request_state(_req(expires_at=now + timedelta(days=1)), now) == "live"


def test_revoked_wins_over_expired():
    from apps.api.routers.requests import request_state
    now = datetime.now(timezone.utc)
    assert request_state(_req(revoked_at=now, expires_at=now - timedelta(days=1)), now) == "revoked"


def test_a_closed_link_answers_410_not_404():
    from apps.api.routers.requests import _live_request
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _req(revoked_at=datetime.now(timezone.utc))
    with pytest.raises(HTTPException) as exc:
        _live_request(db, "t")
    assert exc.value.status_code == 410


def test_an_unknown_link_answers_404():
    from apps.api.routers.requests import _live_request
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        _live_request(db, "nope")
    assert exc.value.status_code == 404


# ── Versions: the same file twice is a V2, never a stray copy ─────────────────

def test_the_same_name_in_another_container_is_the_same_asset():
    from apps.api.routers.requests import asset_name_for
    assert asset_name_for("Hook1.mp4") == asset_name_for("Hook1.mov") == "Hook1"
    assert asset_name_for("../../etc/Hook1.mp4") == "Hook1"
    assert asset_name_for("") == "Untitled"


# ── A token never reaches another folder ──────────────────────────────────────

def test_an_upload_from_another_folder_is_refused():
    from apps.api.routers.requests import _owned_media
    req = _req()
    media = MagicMock(version_id=uuid.uuid4())
    version = MagicMock(asset_id=uuid.uuid4())
    asset = MagicMock(folder_id=uuid.uuid4())         # NOT the request's folder
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [media, version, asset]
    with pytest.raises(HTTPException) as exc:
        _owned_media(db, req, "raw/x")
    assert exc.value.status_code == 403


def test_an_upload_in_the_request_folder_is_allowed():
    from apps.api.routers.requests import _owned_media
    req = _req()
    media = MagicMock(version_id=uuid.uuid4())
    version = MagicMock(asset_id=uuid.uuid4())
    asset = MagicMock(folder_id=req.folder_id)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [media, version, asset]
    assert _owned_media(db, req, "raw/x") == (media, version)


# ── The owner's list fails open ───────────────────────────────────────────────

def test_no_answer_from_the_review_reads_as_ready():
    from apps.api.routers.requests import owner_status
    assert owner_status(None) == {"status": "clear", "open_must_fixes": 0}
    assert owner_status({"status": "weird"})["status"] == "clear"
    assert owner_status({"status": "held", "openMustFixes": 2}) == {"status": "held", "open_must_fixes": 2}


def test_the_bridge_is_silent_when_unconfigured(monkeypatch):
    from apps.api.services import review_bridge
    from apps.api.config import settings
    monkeypatch.setattr(settings, "review_bridge_url", "")
    called = []
    monkeypatch.setattr(review_bridge.httpx, "request", lambda *a, **k: called.append(1))
    assert review_bridge.request_status(["a"]) == {}
    assert review_bridge.register_request("s", "b", "t") is None
    assert called == []


def test_the_bridge_swallows_a_dead_review_service(monkeypatch):
    from apps.api.services import review_bridge
    from apps.api.config import settings
    monkeypatch.setattr(settings, "review_bridge_url", "https://review.invalid")
    monkeypatch.setattr(settings, "review_bridge_secret", "s")

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(review_bridge.httpx, "request", boom)
    assert review_bridge.time_saved(30, None) is None


def test_brand_slugs_match_the_review_service():
    from apps.api.services.review_bridge import brand_slug
    assert brand_slug("MYND Organics GmbH") == "mynd-organics"
    assert brand_slug("Keller Gesundheit") == "keller-gesundheit"


# ── Customers are not staff ───────────────────────────────────────────────────

def _user(is_staff=True, is_superadmin=False):
    u = MagicMock()
    u.id = uuid.uuid4()
    u.is_staff = is_staff
    u.is_superadmin = is_superadmin
    return u


def test_a_customer_does_not_inherit_instance_wide_access(monkeypatch):
    monkeypatch.setattr("apps.api.config.settings.instance_wide_project_access", True)
    from apps.api.services.permissions import implicit_project_role
    assert implicit_project_role(_user(is_staff=False)) is None
    assert implicit_project_role(_user(is_staff=True)) == ProjectRole.editor


def test_a_customer_cannot_open_someone_elses_project(monkeypatch):
    monkeypatch.setattr("apps.api.config.settings.instance_wide_project_access", True)
    from apps.api.services.permissions import require_project_role
    db = MagicMock()
    db.query.return_value = db
    db.filter.return_value = db
    db.first.return_value = None                      # not a member
    with pytest.raises(HTTPException) as exc:
        require_project_role(db, uuid.uuid4(), _user(is_staff=False), ProjectRole.viewer)
    assert exc.value.status_code == 403


def test_a_customer_sees_only_brands_of_its_own_projects():
    from apps.api.routers.requests import _brands_for
    staff = _user(is_staff=True)
    assert _brands_for(MagicMock(), staff) is None      # staff: unfiltered
    db = MagicMock()
    p = MagicMock()
    p.name = "Glow25 GmbH"
    db.query.return_value.filter.return_value.all.side_effect = [[MagicMock(project_id=uuid.uuid4())], [p]]
    assert _brands_for(db, _user(is_staff=False)) == ["glow25"]


def test_self_signup_creates_a_customer_never_staff():
    from apps.api.routers.auth import _create_customer
    db = MagicMock()
    added = []
    db.add.side_effect = added.append
    _create_customer(db, "New@Brand.com")
    assert added[0].is_staff is False
    assert added[0].email == "new@brand.com"


def test_self_signup_is_off_by_default():
    from apps.api.config import Settings
    assert Settings.model_fields["self_signup_enabled"].default is False
