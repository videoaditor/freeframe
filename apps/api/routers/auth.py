from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import logging
import uuid
import secrets
from redis.exceptions import RedisError
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote
from ..database import get_db
from ..schemas.auth import (
    LoginRequest, TokenResponse,
    RefreshRequest, UserResponse, InviteRequest,
    SendMagicCodeRequest, SendMagicCodeResponse,
    VerifyMagicCodeRequest, SetPasswordRequest, GoogleSignInRequest,
    AcceptInviteRequest, InviteInfoResponse,
    ChangePasswordRequest,
)
from ..services.whop_auth import exchange_whop_token, resolve_customer, store_owner_session, require_customer_entitlement
from ..middleware.auth import get_identity_user
from ..services.auth_service import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_user_by_email, get_user_by_id,
)
from ..services import directory_service
from ..services import oidc_auth
from ..services.google_auth import google_enabled, email_from_code
from ..services.redis_service import (
    generate_magic_code, store_magic_code, verify_magic_code as redis_verify_magic_code,
    MAGIC_CODE_EXPIRY_SECONDS, store_oidc_state, consume_oidc_state,
)
from ..tasks.email_tasks import send_magic_code_email, send_invite_email
from ..tasks.celery_app import send_task_safe
from ..models.user import User, UserStatus
from ..middleware.auth import get_current_user
from ..middleware.rate_limit import rate_limit
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

MAGIC_CODE_EXPIRY_MINUTES = MAGIC_CODE_EXPIRY_SECONDS // 60


def _generate_invite_token() -> str:
    """Generate a secure invite token."""
    return secrets.token_urlsafe(48)


def _resolve_against_directory(db: Session, email: str, user: User | None) -> User | None:
    """Reconcile one sign-in address against the external people directory.

    Returns the user allowed to receive a magic code, or None for "no code".

    The directory is consulted on every request rather than only for unknown
    addresses, so access follows the roster continuously instead of being decided
    once, at whatever moment an account happened to be created.

    Four deliberate rules:

    - Superadmins are never gated on the directory. An operator must not be
      lockable out of their own instance by a roster that is maintained
      elsewhere, describes a different population, or simply has them listed
      under some other status.
    - An address the directory says nothing about is left exactly as it was, so
      service accounts and anyone invited by hand keep working.
    - Someone listed under a status outside DIRECTORY_ALLOWED_STATUSES is
      refused, and their account is left untouched. Refusal is stateless, so
      reinstating a person in the directory restores their access with nothing
      to undo here.
    - If the directory can't be reached, existing accounts keep working and
      unknown addresses stay unknown. An outage must never lock out the people
      who can already sign in, nor provision anyone it couldn't vouch for.
    """
    if user is not None and user.is_superadmin:
        return user

    try:
        record = directory_service.find_person(email)
    except directory_service.DirectoryUnavailable:
        return user

    if record is None:
        return user

    if not directory_service.is_allowed(record):
        return None

    if user is not None:
        return user

    user = User(
        email=email,
        name=directory_service.display_name(record, email),
        status=UserStatus.active,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two sign-in attempts raced; the other one created the account.
        db.rollback()
        return get_user_by_email(db, email)
    db.refresh(user)
    logger.info("Provisioned user %s from the people directory", user.id)
    return user


def _create_customer(db: Session, email: str) -> Optional[User]:
    """A self-signed-up customer account: verified by the magic code it is about to receive."""
    # Stored as typed (trimmed), exactly like an invite, so the existing exact-match lookups find it.
    user = User(
        email=email.strip(),
        name=email.split("@")[0][:255] or "New user",
        status=UserStatus.pending_verification,
        is_staff=False,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Someone else holds this address - never hand that account out from a signup path.
        db.rollback()
        return None
    db.refresh(user)
    return user


@router.post("/send-magic-code", response_model=SendMagicCodeResponse, dependencies=[Depends(rate_limit("send_magic_code", 5, 600))])
def send_magic_code(body: SendMagicCodeRequest, db: Session = Depends(get_db)):
    """
    Send magic code to an existing user's email, for login.

    Accounts come from an admin invite (/users/invite), /setup/create-superadmin,
    or - when the instance is configured with one - an external people directory
    that vouches for the address (see _resolve_against_directory).

    Every outcome returns the same response, so this endpoint can't be used to
    enumerate registered emails.
    """
    existing = get_user_by_email(db, body.email)
    user = existing

    if directory_service.is_configured():
        user = _resolve_against_directory(db, body.email, user)

    # Platform v2: someone NEW may sign up as a CUSTOMER. Never staff - they see only what they
    # create. Only when no account exists at all: an existing account the directory just refused
    # stays refused, and is never "re-created". Answers like every other outcome (no enumeration).
    if existing is None and user is None and settings.self_signup_enabled:
        user = _create_customer(db, body.email)

    if not user:
        return SendMagicCodeResponse(
            message="Magic code sent to your email",
            email=body.email,
        )

    # Generate and store magic code in Redis
    code = generate_magic_code()
    store_magic_code(body.email, code)

    # Queue email via Celery (async)
    try:
        send_task_safe(send_magic_code_email, body.email, code, MAGIC_CODE_EXPIRY_MINUTES)
    except Exception:
        pass  # Email delivery is best-effort; code is already in Redis
    
    return SendMagicCodeResponse(
        message="Magic code sent to your email",
        email=body.email,
    )


@router.post("/verify-magic-code", response_model=TokenResponse, dependencies=[Depends(rate_limit("verify_magic_code", 10, 600))])
def verify_magic_code(body: VerifyMagicCodeRequest, db: Session = Depends(get_db)):
    """
    Verify magic code and return tokens.
    Returns needs_password=True if user hasn't set a password yet.
    """
    user = get_user_by_email(db, body.email)
    
    # "No such user" and "deactivated" get the same generic failure as a wrong/expired code —
    # distinguishing them would let a caller enumerate registered or deactivated emails.
    if not user or user.status == UserStatus.deactivated:
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    # Verify magic code from Redis
    success, error = redis_verify_magic_code(body.email, body.code)
    if not success:
        raise HTTPException(status_code=401, detail=error)
    
    # Mark email as verified
    user.email_verified = True
    
    # If user was pending verification, activate them
    if user.status == UserStatus.pending_verification:
        user.status = UserStatus.active
    
    db.commit()
    
    # Check if user needs to set password
    needs_password = settings.password_login_enabled and user.password_hash is None
    
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
        needs_password=needs_password,
    )


@router.get("/google/config")
def google_config():
    """Whether /login shows "Continue with Google". The client id is public by design."""
    enabled = google_enabled()
    return {"enabled": enabled, "client_id": settings.google_client_id if enabled else ""}


@router.post("/google", response_model=TokenResponse, dependencies=[Depends(rate_limit("google_signin", 20, 600))])
def google_sign_in(body: GoogleSignInRequest, db: Session = Depends(get_db)):
    """A Google-verified email signs in exactly like a verified magic code: the same account,
    the same directory rules, and a new customer account only when SELF_SIGNUP_ENABLED."""
    if not google_enabled():
        raise HTTPException(status_code=404, detail="Google sign-in is not configured")
    email = email_from_code(body.code, body.redirect_uri)

    existing = get_user_by_email(db, email)
    user = existing
    if directory_service.is_configured():
        user = _resolve_against_directory(db, email, user)
    if existing is None and user is None and settings.self_signup_enabled:
        user = _create_customer(db, email)
    if not user or user.status == UserStatus.deactivated:
        raise HTTPException(status_code=401, detail="This Google account has no access yet")

    user.email_verified = True
    if user.status == UserStatus.pending_verification:
        user.status = UserStatus.active
    db.commit()
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
        needs_password=False,
    )



# ── Central-gate (OIDC) sign-in ──────────────────────────────────────────────
# Option B (spec #65): terminated here in the Python API, not a Next.js BFF.
# These three endpoints are the entire gate integration; everything downstream
# (session tokens, directory provisioning) reuses the magic-code machinery
# above unchanged. Disabled as a group (404) whenever OIDC isn't configured, so
# a self-hosted instance that hasn't registered with a gate is unaffected.

ACCESS_TOKEN_COOKIE = "ff_access_token"
REFRESH_TOKEN_COOKIE = "ff_refresh_token"
# httpOnly: only this router's own /oidc/logout reads it back (as id_token_hint).
# Unlike the two cookies above, no page JS ever needs to see it.
OIDC_ID_TOKEN_COOKIE = "ff_oidc_id_token"
# Matches the lifetime the web app already gives these cookies when it sets them
# itself after a magic-code sign-in (lib/auth.ts setTokens) - they are a
# presence flag for the Next.js middleware gate, not the credential itself.
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7


def _safe_relative_path(value: str | None, default: str = "/home") -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return default


def _oidc_redirect_uri() -> str:
    return f"{settings.frontend_url.rstrip('/')}/api/auth/oidc/callback"


def _require_oidc_enabled() -> None:
    if not oidc_auth.oidc_enabled():
        raise HTTPException(status_code=404, detail="Gate sign-in is not configured")


def _login_redirect(error: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/login?error={error}", status_code=302)


def _set_session_cookies(response: Response, access: str, refresh: str, id_token: Optional[str]) -> None:
    secure = settings.frontend_url.startswith("https://")
    response.set_cookie(ACCESS_TOKEN_COOKIE, access, max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
                         path="/", httponly=False, samesite="lax", secure=secure)
    response.set_cookie(REFRESH_TOKEN_COOKIE, refresh, max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
                         path="/", httponly=False, samesite="lax", secure=secure)
    if id_token:
        response.set_cookie(OIDC_ID_TOKEN_COOKIE, id_token, max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
                             path="/", httponly=True, samesite="lax", secure=secure)


def _clear_session_cookies(response: Response) -> None:
    for name in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, OIDC_ID_TOKEN_COOKIE):
        response.delete_cookie(name, path="/")


@router.get("/oidc/config")
def oidc_config():
    """Whether /login shows "Sign in with Aditor". No secret is exposed."""
    return {"enabled": oidc_auth.oidc_enabled()}


@router.get("/oidc/login", dependencies=[Depends(rate_limit("oidc_login", 30, 600))])
def oidc_login(from_: Optional[str] = Query(default=None, alias="from")):
    """Build the gate authorize URL (PKCE S256) and 302 there."""
    _require_oidc_enabled()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = oidc_auth.new_pkce_pair()
    try:
        store_oidc_state(state, {
            "verifier": verifier,
            "nonce": nonce,
            "from": _safe_relative_path(from_),
        })
        url = oidc_auth.authorize_url(
            redirect_uri=_oidc_redirect_uri(),
            state=state,
            nonce=nonce,
            code_challenge=challenge,
            resource=settings.frontend_url,
        )
    except (oidc_auth.OIDCError, RedisError):
        logger.warning("Gate OIDC login could not reach the gate or Redis")
        return _login_redirect("gate_sign_in_failed")
    return RedirectResponse(url, status_code=302)


@router.get("/oidc/callback")
def oidc_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Verify state, exchange the code, verify the id_token against the gate's
    JWKS, resolve the reviewer through the existing directory path, and mint
    the existing HS256 session exactly like a verified magic code."""
    _require_oidc_enabled()
    if error or not code or not state:
        return _login_redirect("gate_sign_in_failed")

    try:
        saved = consume_oidc_state(state)
    except RedisError:
        logger.warning("Gate OIDC callback could not reach Redis")
        return _login_redirect("gate_sign_in_failed")
    if not saved:
        return _login_redirect("gate_sign_in_expired")

    try:
        tokens = oidc_auth.exchange_code(
            code=code, redirect_uri=_oidc_redirect_uri(), code_verifier=saved["verifier"],
        )
        id_token = tokens.get("id_token")
        if not isinstance(id_token, str):
            raise oidc_auth.OIDCError("gate token response had no id_token")
        claims = oidc_auth.verify_id_token(
            id_token, nonce=saved["nonce"], access_token=tokens.get("access_token"),
        )
    except (oidc_auth.OIDCError, RedisError) as exc:
        logger.warning("Gate OIDC callback rejected a token: %r / cause=%r", exc, exc.__cause__)
        return _login_redirect("gate_sign_in_failed")

    email = claims["email"].strip()
    existing = get_user_by_email(db, email)
    user = existing
    if directory_service.is_configured():
        user = _resolve_against_directory(db, email, user)

    # No self-signup here, unlike magic-code/Google: the gate is scoped to
    # editor/team sign-in (access policy decided on the gate side), never an
    # open customer-signup funnel.
    if not user or user.status == UserStatus.deactivated:
        return _login_redirect("not_registered")

    user.email_verified = True
    if user.status == UserStatus.pending_verification:
        user.status = UserStatus.active
    db.commit()

    access = create_access_token(str(user.id), token_version=user.token_version)
    refresh = create_refresh_token(str(user.id), token_version=user.token_version)

    response = RedirectResponse(
        f"{settings.frontend_url.rstrip('/')}{saved.get('from') or '/home'}", status_code=302,
    )
    _set_session_cookies(response, access, refresh, id_token)
    return response


@router.get("/oidc/logout")
def oidc_logout(request: Request, from_: Optional[str] = Query(default=None, alias="from")):
    """Clear the FreeFrame session cookies and end the gate's SSO session too.

    Falls back to a plain /login redirect when OIDC isn't configured, so this
    is also safe to use as the *only* sign-out destination regardless of which
    method a given session actually signed in with.
    """
    if oidc_auth.oidc_enabled():
        destination = oidc_auth.end_session_url(
            post_logout_redirect_uri=oidc_auth.signed_out_redirect_uri(),
            id_token_hint=request.cookies.get(OIDC_ID_TOKEN_COOKIE),
        )
    else:
        # Mirrors the plain pre-gate logout redirect: back to /login, optionally
        # remembering the page to return to once signed back in.
        login = f"{settings.frontend_url.rstrip('/')}/login"
        safe_from = from_ if (from_ and from_.startswith("/") and not from_.startswith("//")) else None
        destination = f"{login}?from={quote(safe_from, safe='')}" if safe_from else login
    response = RedirectResponse(destination, status_code=302)
    _clear_session_cookies(response)
    return response


@router.post("/set-password", response_model=UserResponse)
def set_password(
    body: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set password for authenticated user (after magic code verification)."""
    current_user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/invite/{token}", response_model=InviteInfoResponse)
def get_invite_info(token: str, db: Session = Depends(get_db)):
    """Get info about an invite token (for the set-password screen)."""
    user = db.query(User).filter(
        User.invite_token == token,
        User.deleted_at.is_(None),
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Invalid invite link")
    
    if user.invite_token_expires_at and user.invite_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite link expired")
    
    return InviteInfoResponse(
        email=user.email,
        name=user.name,
    )


@router.post("/accept-invite", response_model=TokenResponse)
def accept_invite(body: AcceptInviteRequest, db: Session = Depends(get_db)):
    """Accept invite and set password. Email is already verified via invite."""
    user = db.query(User).filter(
        User.invite_token == body.token,
        User.deleted_at.is_(None),
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Invalid invite link")
    
    if user.invite_token_expires_at and user.invite_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite link expired")
    
    # Set password and activate user
    user.password_hash = hash_password(body.password)
    user.email_verified = True  # Invited users are pre-verified
    user.status = UserStatus.active
    user.invite_token = None
    user.invite_token_expires_at = None
    db.commit()
    
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
        needs_password=False,
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit("login", 10, 600))])
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Login with email + password."""
    if not settings.password_login_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    user = get_user_by_email(db, body.email)
    if (
        not user
        or not user.password_hash
        or not verify_password(body.password, user.password_hash)
        or user.status == UserStatus.deactivated
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
        needs_password=False,
    )


@router.post("/whop", response_model=TokenResponse, dependencies=[Depends(rate_limit("whop_signin", 300, 60))])
def whop_session(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("x-whop-user-token")
    if not token:
        raise HTTPException(401, "Open Aditor Review from Whop to sign in")
    owner = exchange_whop_token(token)
    user = resolve_customer(db, owner)
    store_owner_session(user, owner)
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
        needs_password=False,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user or user.status == UserStatus.deactivated:
        raise HTTPException(status_code=401, detail="User not found")
    require_customer_entitlement(user, allow_expired=True)
    if payload.get("ver", 1) != user.token_version:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
        needs_password=user.password_hash is None,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_identity_user)):
    return current_user


@router.get('/campaign')
def campaign_status(db: Session = Depends(get_db), current_user: User = Depends(get_identity_user)):
    from ..services.campaign_access import context
    from ..services.campaign_usage import refresh_usage, recommendation
    campaign = context(current_user)
    if campaign is None:
        return {'campaign': None}
    count = refresh_usage(db, current_user)
    return {'campaign': campaign, 'reviewedAds': count, 'recommendedPlan': recommendation(count)}


@router.patch("/me/preferences", response_model=UserResponse)
def update_preferences(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user preferences (theme, etc). Merges with existing preferences."""
    current_prefs = current_user.preferences or {}
    current_prefs.update(body)
    current_user.preferences = current_prefs
    # Force SQLAlchemy to detect the JSON change
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(current_user, "preferences")
    db.commit()
    db.refresh(current_user)
    return current_user

@router.patch("/change-password", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change password for authenticated user."""
    if current_user.password_hash is None:
        raise HTTPException(status_code=400, detail="No password set for this account; use set-password instead")
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = hash_password(body.new_password)
    current_user.token_version += 1
    db.commit()
    db.refresh(current_user)
    return TokenResponse(
        access_token=create_access_token(str(current_user.id), token_version=current_user.token_version),
        refresh_token=create_refresh_token(str(current_user.id), token_version=current_user.token_version),
        needs_password=False,
    )
