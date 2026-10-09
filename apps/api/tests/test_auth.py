"""
Auth endpoint tests.

The DB is fully mocked; we control what `query().filter().first()` returns
to simulate existing / non-existing users.

Password hashing (passlib/bcrypt) is mocked because the local environment has
a bcrypt version that is incompatible with passlib. The hash/verify logic is
unit-tested separately in test_auth_service.py.
"""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from apps.api.models.user import UserStatus


_FAKE_HASH = "$2b$12$fakehashforteststhatisnotrealatall00000000000000000000"


def _mock_user(
    email: str = "test@example.com",
    password_hash: str = _FAKE_HASH,
) -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = email
    u.name = "Test User"
    u.password_hash = password_hash
    u.status = UserStatus.active
    u.is_superadmin = False
    u.avatar_url = None
    u.token_version = 1
    u.created_at = datetime.now(timezone.utc)
    u.deleted_at = None
    return u


# Patch bcrypt verification so tests don't depend on the local bcrypt installation.
_VERIFY_PATCH = "apps.api.routers.auth.verify_password"


def test_login_success(client, mock_db):
    """POST /auth/login — happy path returns access_token."""
    user = _mock_user("login@example.com")
    mock_db.first.return_value = user

    with patch(_VERIFY_PATCH, return_value=True):
        resp = client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "pw123456"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client, mock_db):
    """POST /auth/login — 401 on wrong password."""
    user = _mock_user("wp@example.com")
    mock_db.first.return_value = user

    with patch(_VERIFY_PATCH, return_value=False):
        resp = client.post(
            "/auth/login",
            json={"email": "wp@example.com", "password": "wrong"},
        )

    assert resp.status_code == 401


def test_login_nonexistent_user(client, mock_db):
    """POST /auth/login — 401 when user not found."""
    mock_db.first.return_value = None

    resp = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "anypassword"},
    )
    assert resp.status_code == 401


def test_register_endpoint_removed(client):
    """POST /auth/register — endpoint has been removed (was an unauthenticated, un-invite-gated
    account creation path; GHSA-9m78-fww2-p89h). 404, not 405: the route no longer exists."""
    resp = client.post(
        "/auth/register",
        json={"email": "newuser@example.com", "name": "New User", "password": "securepassword"},
    )
    assert resp.status_code == 404


def test_users_batch_does_not_leak_invite_token(client, auth_headers, mock_db, test_user):
    """GET /users — never includes invite_token, even for a caller with no admin rights.

    Regression test: GET /users and GET /users/search reused UserResponse (which included
    invite_token) behind only get_current_user, so any authenticated user could read a
    pending invitee's live token and hijack the invite via /auth/accept-invite before the
    real invitee acted (GHSA-9m78-fww2-p89h).
    """
    test_user.is_superadmin = False
    target = _mock_user("invitee@example.com")
    target.status = UserStatus.pending_invite
    target.is_superadmin = False
    target.email_verified = False
    target.preferences = {}
    target.invite_token = "super-secret-invite-token"
    mock_db.all.return_value = [target]

    resp = client.get(f"/users?ids={target.id}", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "invite_token" not in body[0]


def test_admin_list_users_still_includes_invite_token(client, auth_headers, mock_db, test_user):
    """GET /admin/users — admin-gated, so it may still expose invite_token (needed for the
    admin "copy invite link" UI); this endpoint's own is_superadmin check is the gate."""
    test_user.is_superadmin = True
    target = _mock_user("invitee@example.com")
    target.status = UserStatus.pending_invite
    target.is_superadmin = False
    target.email_verified = False
    target.preferences = {}
    target.invite_token = "super-secret-invite-token"
    mock_db.all.return_value = [target]

    resp = client.get("/admin/users", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["invite_token"] == "super-secret-invite-token"


def test_get_me(client, auth_headers, test_user):
    """GET /auth/me — returns current user profile."""
    resp = client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == test_user.email


def test_refresh_token(client, mock_db):
    """POST /auth/refresh — valid refresh token returns new access_token."""
    from apps.api.services.auth_service import create_refresh_token

    user = _mock_user("ref@example.com")
    refresh = create_refresh_token(str(user.id))
    mock_db.first.return_value = user

    resp = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_refresh_token_invalid(client, mock_db):
    """POST /auth/refresh — bad token returns 401."""
    resp = client.post("/auth/refresh", json={"refresh_token": "not-a-valid-token"})
    assert resp.status_code == 401


def test_get_me_no_auth(client):
    """GET /auth/me without token should return 401 or 403 (no bearer scheme)."""
    resp = client.get("/auth/me")
    assert resp.status_code in (401, 403)


def test_change_password_invalid_length(client, auth_headers):
    """Test that passwords under 8 characters are rejected by Pydantic."""
    payload = {
        "current_password": "ValidPassword123!",
        "new_password": "short" # 5 characters
    }
    
    response = client.patch("/auth/change-password", json=payload, headers=auth_headers)
    
    assert response.status_code == 422
    assert "new_password" in response.text

def test_refresh_token_rejected_after_password_change(client, mock_db):
    """Test that an old refresh token is rejected if the token_version has incremented."""
    from apps.api.services.auth_service import create_refresh_token
    
    # 1. Use the file's mock helper, but simulate a password change by bumping the version to 2
    mock_user = _mock_user("test@example.com")
    mock_user.token_version = 2 
    
    # Configure the mock_db to return this user
    mock_db.first.return_value = mock_user

    # 2. Create a "stolen" refresh token that was minted when the version was 1
    stolen_token = create_refresh_token(str(mock_user.id), token_version=1)

    # 3. Attempt to refresh the session
    response = client.post("/auth/refresh", json={"refresh_token": stolen_token})
    
    # 4. Assert the request is blocked
    assert response.status_code == 401
    assert response.json()["detail"] == "Session expired, please log in again"

def test_refresh_token_legacy_token_accepted(client, mock_db):
    """Test that a token without a 'ver' claim is treated as version 1 and accepted."""
    from apps.api.config import settings
    from jose import jwt
    
    mock_user = _mock_user("legacy@example.com")
    mock_user.token_version = 1
    mock_db.first.return_value = mock_user
    
    # Manually mint a JWT that completely lacks the "ver" claim
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    legacy_token = jwt.encode({"sub": str(mock_user.id), "type": "refresh", "exp": expire}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    
    response = client.post("/auth/refresh", json={"refresh_token": legacy_token})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_change_password_increments_version(client, auth_headers, test_user, mock_db):
    """Test that changing password bumps token_version and returns fresh tokens."""
    
    # Explicitly set the token_version so the endpoint doesn't crash on `None += 1`
    test_user.token_version = 1
    mock_db.commit()
    mock_db.refresh(test_user)
    
    initial_version = test_user.token_version
    
    with patch("apps.api.routers.auth.verify_password", return_value=True), \
         patch("apps.api.routers.auth.hash_password", return_value=_FAKE_HASH):
        
        payload = {
            "current_password": "AnyOldPassword123!",
            "new_password": "NewValidPassword123!"
        }
        response = client.patch("/auth/change-password", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

        mock_db.refresh(test_user)
        assert test_user.token_version == initial_version + 1


def test_delete_user_rejects_self(client, auth_headers, test_user):
    """DELETE /users/{id} — an admin can't delete their own account. Matches the
    self-protection already on /admin/users/{id}/deactivate; without it, a superadmin
    (accidentally or via a compromised session) could lock themselves out irrecoverably,
    since /setup/create-superadmin only checks is_superadmin, not soft-deletion."""
    test_user.is_superadmin = True
    resp = client.delete(f"/users/{test_user.id}", headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Directory-backed provisioning (DIRECTORY_LOOKUP_URL)
# ---------------------------------------------------------------------------
#
# The endpoint auto-creating accounts is exactly what GHSA-9m78-fww2-p89h was
# about. The gate callback (apps/api/routers/auth.py's oidc_callback) is now the
# only sign-in route that reaches `_resolve_against_directory`, and the full set
# of provisioning/refusal/outage/superadmin-bypass regression tests for it lives
# in test_oidc_router.py.


def test_directory_allowed_statuses_parsing():
    """The setting is a set, parsed case- and whitespace-insensitively."""
    from apps.api.services import directory_service as ds

    with patch.object(ds.settings, "directory_allowed_statuses", " Active , paused ,, ONBOARDING "):
        assert ds.allowed_statuses() == {"active", "paused", "onboarding"}
        assert ds.is_allowed({"status": "Paused"}) is True
        assert ds.is_allowed({"status": "archived"}) is False
        assert ds.is_allowed({}) is False

    # An empty set means the directory has no notion of status and vouches for
    # everyone it lists, rather than silently refusing everyone.
    with patch.object(ds.settings, "directory_allowed_statuses", ""):
        assert ds.is_allowed({"status": "anything"}) is True


def test_access_token_stays_short_lived():
    """Session length and credential length are different dials.

    `token_version` is only checked when refreshing (see `refresh_token`), so a
    live access token cannot be revoked - its lifetime *is* the revocation
    window. It also travels in the EventSource query string, which the reverse
    proxy writes to its access log, so a long-lived one turns every log line and
    every log backup into a working credential. Keeping people signed in is the
    refresh token's job; it goes to a single endpoint, rotates on use, and is
    version-checked. If someone reaches for the first number to stop editors
    re-authenticating, this test is here to send them to the second one.
    """
    from apps.api.config import settings

    assert settings.access_token_expire_minutes <= 120
    assert settings.refresh_token_expire_days >= 1
