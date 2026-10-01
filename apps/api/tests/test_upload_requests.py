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


# ── The owner's list requires review evidence ───────────────────────────────────────────────

def test_no_answer_from_the_review_reads_as_unavailable():
    from apps.api.routers.requests import _request_gate
    assets = [{'review_state': 'clear'}]
    assert _request_gate(assets, None) == {"status": "unavailable", "open_must_fixes": 0}
    assert _request_gate(assets, {"status": "weird"})["status"] == "unavailable"
    assert _request_gate(assets, {"status": "held", "openMustFixes": 2}) == {"status": "held", "open_must_fixes": 2}


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
    assert added[0].email == "New@Brand.com"   # stored as typed, like an invite, so exact-match lookups find it


def test_self_signup_is_off_by_default():
    from apps.api.config import Settings
    assert Settings.model_fields["self_signup_enabled"].default is False


def test_an_objection_about_another_folders_file_is_refused(monkeypatch):
    from apps.api.routers import requests as rq
    req = _req()
    monkeypatch.setattr(rq, "_live_request", lambda db, token: req)
    asset = MagicMock(folder_id=uuid.uuid4())       # not this request's folder
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = asset
    called = []
    monkeypatch.setattr(rq.review_bridge, "object_to_note", lambda *a: called.append(a))
    with pytest.raises(HTTPException) as exc:
        rq.guest_object("t", rq.GuestObjection(asset_id=uuid.uuid4(), text="The price is on screen at 0:14."), db)
    assert exc.value.status_code == 403
    assert called == []


# ── Ranking editors by accuracy ───────────────────────────────────────────────

def test_editors_are_ranked_by_first_try_accuracy():
    from apps.api.routers.requests import rank_editors
    uploads = [
        {"email": "a@x.com", "name": "Alfredo", "asset_id": "1"},
        {"email": "a@x.com", "name": "Alfredo", "asset_id": "1"},   # his v2 of the same video
        {"email": "a@x.com", "name": "Alfredo", "asset_id": "2"},
        {"email": "s@x.com", "name": "Sandra", "asset_id": "3"},
        {"email": "n@x.com", "name": "New", "asset_id": "4"},
    ]
    stats = {
        "1": {"versions": 2, "v1MustFix": 2, "openMustFix": 0},
        "2": {"versions": 1, "v1MustFix": 0, "openMustFix": 0},
        "3": {"versions": 1, "v1MustFix": 0, "openMustFix": 0},
    }
    r = rank_editors(uploads, stats)
    assert [x["name"] for x in r] == ["Sandra", "Alfredo", "New"]
    alfredo = r[1]
    assert alfredo["videos"] == 2                    # a V2 is not a second video
    assert alfredo["first_try_rate"] == 0.5
    assert alfredo["avg_versions"] == 1.5
    assert r[2]["first_try_rate"] is None            # not reviewed yet: ranked last, not as 0%


def test_a_larger_sample_wins_a_tie():
    from apps.api.routers.requests import rank_editors
    uploads = [{"email": "one@x", "name": "One", "asset_id": "1"},
               {"email": "many@x", "name": "Many", "asset_id": "2"}, {"email": "many@x", "name": "Many", "asset_id": "3"}]
    stats = {k: {"versions": 1, "v1MustFix": 0, "openMustFix": 0} for k in "123"}
    assert [x["name"] for x in rank_editors(uploads, stats)] == ["Many", "One"]


# ── Review findings (2026-09-28) ──────────────────────────────────────────────

def test_a_customer_brand_is_namespaced_never_its_typed_name():
    from apps.api.routers.requests import project_brand
    project = MagicMock()
    project.id = uuid.uuid4()
    project.name = "Freiheit"                      # would resolve onto freiheit-media by name
    customer = MagicMock(is_staff=False)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = customer
    assert project_brand(db, project) == f"cust-{project.id.hex[:16]}"


def test_a_staff_workspace_keeps_its_name_and_is_never_empty():
    from apps.api.routers.requests import project_brand
    project = MagicMock()
    project.id = uuid.uuid4()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock(is_staff=True)
    project.name = "Glow25"
    assert project_brand(db, project) == "glow25"
    project.name = "GmbH"
    assert project_brand(db, project).startswith("cust-")


def test_a_refused_staff_account_is_never_recreated_by_signup(monkeypatch):
    from apps.api.routers import auth
    staff = MagicMock(is_staff=True, is_superadmin=False)
    monkeypatch.setattr(auth, "get_user_by_email", lambda db, e: staff)
    monkeypatch.setattr(auth.directory_service, "is_configured", lambda: True)
    monkeypatch.setattr(auth, "_resolve_against_directory", lambda db, e, u: None)   # roster says: gone
    monkeypatch.setattr(auth.settings, "self_signup_enabled", True)
    created = []
    monkeypatch.setattr(auth, "_create_customer", lambda db, e: created.append(e))
    monkeypatch.setattr(auth, "store_magic_code", lambda *a: pytest.fail("no code may be stored"))
    auth.send_magic_code(auth.SendMagicCodeRequest(email="gone@aditor.ai"), MagicMock())
    assert created == []


def test_signup_never_hands_out_an_existing_account():
    from sqlalchemy.exc import IntegrityError
    from apps.api.routers.auth import _create_customer
    db = MagicMock()
    db.commit.side_effect = IntegrityError("dup", {}, Exception())
    assert _create_customer(db, "taken@x.com") is None


def test_a_customer_gets_no_people_directory():
    from apps.api.routers.users import search_users
    assert search_users(q="a", db=MagicMock(), current_user=MagicMock(is_staff=False)) == []


def test_public_projects_are_a_staff_thing(monkeypatch):
    from apps.api.services import permissions
    monkeypatch.setattr(permissions, "is_public_project", lambda db, pid, user: True)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    asset = MagicMock(project_id=uuid.uuid4())
    customer = MagicMock(is_staff=False, is_superadmin=False)
    assert permissions.is_staff(customer) is False
    assert permissions.is_staff(MagicMock(is_staff=True)) is True
