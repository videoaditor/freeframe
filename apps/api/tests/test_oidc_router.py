"""Central-gate OIDC router: GET /auth/oidc/{config,login,callback,logout}.

The crypto/JWKS verification itself is covered in test_oidc_auth.py; these
tests exercise the HTTP wiring - redirects, cookies, state handling, and the
directory-refusal path - with oidc_auth's network calls mocked out.
"""
import contextlib
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from apps.api.models.user import UserStatus
from apps.api.services import oidc_auth
from apps.api.services.directory_service import DirectoryUnavailable

RL = "apps.api.middleware.rate_limit.check_rate_limit"
ISSUER = "https://auth.aditor.ai"
FRONTEND = "https://feedback.aditor.ai"


def _user(status=UserStatus.active, superadmin=False):
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "max@aditor.ai"
    u.name = "Max"
    u.status = status
    u.is_superadmin = superadmin
    u.token_version = 1
    u.created_at = datetime.now(timezone.utc)
    u.deleted_at = None
    return u


@pytest.fixture
def oidc_on():
    with patch("apps.api.routers.auth.settings.oidc_issuer", ISSUER), \
         patch("apps.api.routers.auth.settings.oidc_client_id", "freeframe-web"), \
         patch("apps.api.routers.auth.settings.oidc_client_secret", "shh"), \
         patch("apps.api.routers.auth.settings.frontend_url", FRONTEND), \
         patch(RL, return_value=(True, 0)):
        yield


def test_config_reports_disabled_by_default(client):
    with patch("apps.api.routers.auth.settings.oidc_issuer", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_id", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_secret", ""):
        assert client.get("/auth/oidc/config").json() == {"enabled": False}


def test_config_reports_enabled(client, oidc_on):
    assert client.get("/auth/oidc/config").json() == {"enabled": True}


def test_login_404_when_disabled(client):
    with patch("apps.api.routers.auth.settings.oidc_issuer", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_id", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_secret", ""), \
         patch(RL, return_value=(True, 0)):
        resp = client.get("/auth/oidc/login")
    assert resp.status_code == 404


def test_callback_404_when_disabled(client):
    with patch("apps.api.routers.auth.settings.oidc_issuer", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_id", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_secret", ""):
        resp = client.get("/auth/oidc/callback?code=c&state=s")
    assert resp.status_code == 404


def test_login_redirects_to_gate_with_pkce_state(client, oidc_on):
    with patch("apps.api.services.oidc_auth._discovery",
               return_value={"authorization_endpoint": f"{ISSUER}/authorize"}), \
         patch("apps.api.routers.auth.store_oidc_state") as store:
        resp = client.get("/auth/oidc/login?from=%2Fhandin", follow_redirects=False)

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith(f"{ISSUER}/authorize?")
    qs = parse_qs(urlparse(location).query)
    assert qs["client_id"] == ["freeframe-web"]
    assert qs["redirect_uri"] == [f"{FRONTEND}/api/auth/oidc/callback"]
    assert qs["code_challenge_method"] == ["S256"]
    assert qs["resource"] == [FRONTEND]
    assert "code_challenge" in qs and "state" in qs and "nonce" in qs

    store.assert_called_once()
    state_arg, data_arg = store.call_args.args
    assert state_arg == qs["state"][0]
    assert data_arg["nonce"] == qs["nonce"][0]
    assert data_arg["from"] == "/handin"
    assert "verifier" in data_arg


def test_login_rejects_an_unsafe_from_and_defaults_home(client, oidc_on):
    with patch("apps.api.services.oidc_auth._discovery",
               return_value={"authorization_endpoint": f"{ISSUER}/authorize"}), \
         patch("apps.api.routers.auth.store_oidc_state") as store:
        client.get("/auth/oidc/login?from=https://evil.example", follow_redirects=False)
    _, data_arg = store.call_args.args
    assert data_arg["from"] == "/home"


def _callback(client, **overrides):
    saved = {"verifier": "v", "nonce": "n", "from": "/home"}
    saved.update(overrides.pop("saved", {}))
    claims = {"email": "max@aditor.ai"}
    claims.update(overrides.pop("claims", {}))
    with patch("apps.api.routers.auth.consume_oidc_state", return_value=saved), \
         patch("apps.api.routers.auth.oidc_auth.exchange_code", return_value={"id_token": "idt"}), \
         patch("apps.api.routers.auth.oidc_auth.verify_id_token", return_value=claims):
        return client.get("/auth/oidc/callback?code=c&state=s", follow_redirects=False)


def test_callback_signs_in_an_existing_active_user(client, mock_db, oidc_on):
    mock_db.first.return_value = _user()
    resp = _callback(client)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{FRONTEND}/home"
    assert resp.cookies.get("ff_access_token")
    assert resp.cookies.get("ff_refresh_token")
    assert resp.cookies.get("ff_oidc_id_token") == "idt"


def test_callback_honors_the_saved_return_path(client, mock_db, oidc_on):
    mock_db.first.return_value = _user()
    resp = _callback(client, saved={"from": "/handin"})
    assert resp.headers["location"] == f"{FRONTEND}/handin"


def test_callback_refuses_an_unregistered_email(client, mock_db, oidc_on):
    mock_db.first.return_value = None
    resp = _callback(client)
    assert resp.headers["location"] == f"{FRONTEND}/login?error=not_registered"
    assert not resp.cookies.get("ff_access_token")


def test_callback_refuses_a_deactivated_user(client, mock_db, oidc_on):
    mock_db.first.return_value = _user(status=UserStatus.deactivated)
    resp = _callback(client)
    assert resp.headers["location"] == f"{FRONTEND}/login?error=not_registered"


def test_callback_rejects_when_the_gate_reports_an_error(client, oidc_on):
    resp = client.get("/auth/oidc/callback?error=access_denied", follow_redirects=False)
    assert resp.headers["location"] == f"{FRONTEND}/login?error=gate_sign_in_failed"


def test_callback_rejects_an_unknown_or_expired_state(client, oidc_on):
    with patch("apps.api.routers.auth.consume_oidc_state", return_value=None):
        resp = client.get("/auth/oidc/callback?code=c&state=bogus", follow_redirects=False)
    assert resp.headers["location"] == f"{FRONTEND}/login?error=gate_sign_in_expired"


def test_callback_rejects_a_token_that_fails_verification(client, mock_db, oidc_on):
    """Covers the acceptance requirement that a tampered/expired gate id_token
    is rejected - the signature/claims checks themselves are unit-tested in
    test_oidc_auth.py; here we confirm the router routes that failure to the
    same generic refusal as every other callback error."""
    saved = {"verifier": "v", "nonce": "n", "from": "/home"}
    with patch("apps.api.routers.auth.consume_oidc_state", return_value=saved), \
         patch("apps.api.routers.auth.oidc_auth.exchange_code", return_value={"id_token": "idt"}), \
         patch("apps.api.routers.auth.oidc_auth.verify_id_token", side_effect=oidc_auth.OIDCError("bad")):
        resp = client.get("/auth/oidc/callback?code=c&state=s", follow_redirects=False)
    assert resp.headers["location"] == f"{FRONTEND}/login?error=gate_sign_in_failed"
    assert not resp.cookies.get("ff_access_token")


def test_callback_rejects_a_token_exchange_failure(client, oidc_on):
    saved = {"verifier": "v", "nonce": "n", "from": "/home"}
    with patch("apps.api.routers.auth.consume_oidc_state", return_value=saved), \
         patch("apps.api.routers.auth.oidc_auth.exchange_code", side_effect=oidc_auth.OIDCError("x")):
        resp = client.get("/auth/oidc/callback?code=c&state=s", follow_redirects=False)
    assert resp.headers["location"] == f"{FRONTEND}/login?error=gate_sign_in_failed"


def test_logout_ends_the_gate_sso_session(client, oidc_on):
    with patch("apps.api.services.oidc_auth._discovery",
               return_value={"end_session_endpoint": f"{ISSUER}/endsession"}):
        resp = client.get("/auth/oidc/logout", cookies={"ff_oidc_id_token": "idt"}, follow_redirects=False)

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith(f"{ISSUER}/endsession?")
    qs = parse_qs(urlparse(location).query)
    assert qs["id_token_hint"] == ["idt"]
    assert qs["post_logout_redirect_uri"] == [f"{ISSUER}/signed-out"]

    set_cookie = " ".join(resp.headers.get_list("set-cookie"))
    for name in ("ff_access_token", "ff_refresh_token", "ff_oidc_id_token"):
        assert f"{name}=" in set_cookie
    assert "Max-Age=0" in set_cookie


def test_logout_falls_back_to_login_when_unconfigured(client):
    with patch("apps.api.routers.auth.settings.oidc_issuer", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_id", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_secret", ""), \
         patch("apps.api.routers.auth.settings.frontend_url", FRONTEND):
        resp = client.get("/auth/oidc/logout", follow_redirects=False)
    assert resp.headers["location"] == f"{FRONTEND}/login"


def test_logout_fallback_preserves_from(client):
    with patch("apps.api.routers.auth.settings.oidc_issuer", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_id", ""), \
         patch("apps.api.routers.auth.settings.oidc_client_secret", ""), \
         patch("apps.api.routers.auth.settings.frontend_url", FRONTEND):
        resp = client.get("/auth/oidc/logout?from=%2Fhandin", follow_redirects=False)
    assert resp.headers["location"] == f"{FRONTEND}/login?from=%2Fhandin"


# ---------------------------------------------------------------------------
# Directory-backed provisioning (DIRECTORY_LOOKUP_URL), reached through the
# gate callback.
# ---------------------------------------------------------------------------
#
# The endpoint auto-creating accounts is exactly what GHSA-9m78-fww2-p89h was
# about, so these pin down that it only ever happens for an address an
# operator-configured directory actively vouches for, and never otherwise.
# Formerly exercised through the (now removed) magic-code endpoint; the gate
# callback shares the same _resolve_against_directory helper.

_DIR = "apps.api.routers.auth.directory_service"


def _directory(record=None, unavailable=False):
    """Patch the directory as configured, answering with `record`."""

    @contextlib.contextmanager
    def _ctx():
        with patch(f"{_DIR}.is_configured", return_value=True), \
             patch(f"{_DIR}.find_person",
                   side_effect=DirectoryUnavailable("boom") if unavailable else None,
                   return_value=record):
            yield

    return _ctx()


def test_callback_provisions_person_the_directory_vouches_for(client, mock_db, oidc_on):
    """An unknown address listed as active in the directory gets an account and signs in."""
    mock_db.first.return_value = None

    with _directory({"full_name": "Saskia Ramsauer", "status": "active"}):
        resp = _callback(client)

    assert resp.headers["location"] == f"{FRONTEND}/home"
    mock_db.add.assert_called_once()
    created = mock_db.add.call_args[0][0]
    assert created.email == "max@aditor.ai"
    assert created.status == UserStatus.active


def test_callback_refuses_person_whose_status_is_not_allowed(client, mock_db, oidc_on):
    """A listed person outside the allowed statuses is refused, and their account is untouched."""
    user = _user()
    mock_db.first.return_value = user

    with _directory({"full_name": "Archived Person", "status": "archived"}):
        resp = _callback(client)

    assert resp.headers["location"] == f"{FRONTEND}/login?error=not_registered"
    assert user.status == UserStatus.active  # refusal is stateless, nothing is mutated
    mock_db.commit.assert_not_called()


def test_callback_leaves_addresses_the_directory_does_not_know_alone(client, mock_db, oidc_on):
    """Operator and service accounts appear on no roster, so omission must not lock them out."""
    user = _user()
    mock_db.first.return_value = user

    with _directory(None):
        resp = _callback(client)

    assert resp.headers["location"] == f"{FRONTEND}/home"
    assert resp.cookies.get("ff_access_token")


def test_callback_survives_a_directory_outage_for_existing_users(client, mock_db, oidc_on):
    """A directory that can't be reached must not lock out people who can already sign in."""
    user = _user()
    mock_db.first.return_value = user

    with _directory(unavailable=True):
        resp = _callback(client)

    assert resp.headers["location"] == f"{FRONTEND}/home"


def test_callback_does_not_provision_during_a_directory_outage(client, mock_db, oidc_on):
    """An unreachable directory vouches for nobody, so no account may be created on its word."""
    mock_db.first.return_value = None

    with _directory(unavailable=True):
        resp = _callback(client)

    assert resp.headers["location"] == f"{FRONTEND}/login?error=not_registered"
    mock_db.add.assert_not_called()


def test_callback_never_gates_a_superadmin_on_the_directory(client, mock_db, oidc_on):
    """The operator must stay reachable even when the roster lists them as inactive."""
    user = _user(superadmin=True)
    mock_db.first.return_value = user

    with _directory({"full_name": "Owner", "status": "paused"}):
        resp = _callback(client)

    assert resp.headers["location"] == f"{FRONTEND}/home"


def test_callback_allows_a_status_in_the_configured_set(client, mock_db, oidc_on):
    """A roster's "not working right now" state must not cost someone their sign-in.

    Regression test for shipping DIRECTORY_ALLOWED_STATUSES=active against a roster
    where `paused` means "between assignments", which locked out 29 of 76 people who
    were still very much employed.
    """
    mock_db.first.return_value = None

    with patch("apps.api.services.directory_service.settings.directory_allowed_statuses",
               "active,paused,onboarding"), \
         patch(f"{_DIR}.is_configured", return_value=True), \
         patch(f"{_DIR}.find_person", return_value={"full_name": "Between Jobs", "status": "paused"}):
        resp = _callback(client)

    assert resp.headers["location"] == f"{FRONTEND}/home"
    mock_db.add.assert_called_once()
