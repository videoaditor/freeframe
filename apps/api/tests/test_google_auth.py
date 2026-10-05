"""Google sign-in: claim checks (pure) and the /auth/google route (mocked DB + Google)."""
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.api.models.user import UserStatus
from apps.api.services.google_auth import verified_email

CID = "cid.apps.googleusercontent.com"
RL = "apps.api.middleware.rate_limit.check_rate_limit"


def _claims(**over):
    c = {"aud": CID, "iss": "https://accounts.google.com", "exp": time.time() + 300,
         "email": "max@nordicskin.de", "email_verified": True}
    c.update(over)
    return c


def test_verified_email_accepts_good_claims():
    assert verified_email(_claims(), CID) == "max@nordicskin.de"
    assert verified_email(_claims(iss="accounts.google.com", email_verified="true"), CID) == "max@nordicskin.de"


@pytest.mark.parametrize("over", [
    {"aud": "someone-else"}, {"iss": "https://evil.example"}, {"exp": time.time() - 1},
    {"email_verified": False}, {"email": None},
])
def test_verified_email_rejects_bad_claims(over):
    assert verified_email(_claims(**over), CID) is None


def _user(status=UserStatus.active):
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "max@nordicskin.de"
    u.name = "Max"
    u.status = status
    u.is_superadmin = False
    u.token_version = 1
    u.created_at = datetime.now(timezone.utc)
    u.deleted_at = None
    return u


@pytest.fixture
def google_on():
    with patch("apps.api.routers.auth.google_enabled", return_value=True), \
         patch("apps.api.routers.auth.email_from_code", return_value="max@nordicskin.de"), \
         patch(RL, return_value=(True, 0)):
        yield


def _post(client):
    return client.post("/auth/google", json={"code": "c", "redirect_uri": "https://x/login/google"})


def test_existing_user_signs_in(client, mock_db, google_on):
    mock_db.first.return_value = _user()
    resp = _post(client)
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_pending_user_is_activated(client, mock_db, google_on):
    user = _user(UserStatus.pending_verification)
    mock_db.first.return_value = user
    assert _post(client).status_code == 200
    assert user.status == UserStatus.active and user.email_verified is True


def test_new_user_gets_customer_account_when_self_signup_on(client, mock_db, google_on):
    mock_db.first.return_value = None
    new = _user()
    with patch("apps.api.routers.auth.settings.self_signup_enabled", True), \
         patch("apps.api.routers.auth._create_customer", return_value=new) as create:
        resp = _post(client)
    assert resp.status_code == 200
    create.assert_called_once()


def test_new_user_refused_when_self_signup_off(client, mock_db, google_on):
    mock_db.first.return_value = None
    with patch("apps.api.routers.auth.settings.self_signup_enabled", False), \
         patch("apps.api.routers.auth._create_customer") as create:
        resp = _post(client)
    assert resp.status_code == 401
    create.assert_not_called()


def test_deactivated_user_refused(client, mock_db, google_on):
    mock_db.first.return_value = _user(UserStatus.deactivated)
    assert _post(client).status_code == 401


def test_bad_google_code_is_401(client, mock_db):
    with patch("apps.api.routers.auth.google_enabled", return_value=True), \
         patch("apps.api.routers.auth.email_from_code", side_effect=HTTPException(401, "x")), \
         patch(RL, return_value=(True, 0)):
        assert _post(client).status_code == 401


def test_unconfigured(client):
    with patch("apps.api.routers.auth.google_enabled", return_value=False), patch(RL, return_value=(True, 0)):
        assert _post(client).status_code == 404
        assert client.get("/auth/google/config").json() == {"enabled": False, "client_id": ""}


def test_email_from_code_exchanges_and_checks_claims():
    from jose import jwt as jose_jwt
    from apps.api.services import google_auth
    good = MagicMock(status_code=200)
    good.json.return_value = {"id_token": jose_jwt.encode(_claims(), "k", algorithm="HS256")}
    with patch.object(google_auth.settings, "google_client_id", CID), \
         patch.object(google_auth.settings, "google_client_secret", "s"), \
         patch("apps.api.services.google_auth.httpx.post", return_value=good) as post:
        assert google_auth.email_from_code("c", "https://x/login/google") == "max@nordicskin.de"
    assert post.call_args.kwargs["data"]["client_secret"] == "s"

    bad = MagicMock(status_code=400)
    with patch.object(google_auth.settings, "google_client_id", CID), \
         patch("apps.api.services.google_auth.httpx.post", return_value=bad):
        with pytest.raises(HTTPException):
            google_auth.email_from_code("c", "https://x/login/google")
