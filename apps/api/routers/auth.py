from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import logging
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from ..database import get_db
from ..schemas.auth import (
    LoginRequest, TokenResponse,
    RefreshRequest, UserResponse, InviteRequest,
    SendMagicCodeRequest, SendMagicCodeResponse,
    VerifyMagicCodeRequest, SetPasswordRequest,
    AcceptInviteRequest, InviteInfoResponse,
    ChangePasswordRequest,
)
from ..services.auth_service import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_user_by_email, get_user_by_id,
)
from ..services import directory_service
from ..services.redis_service import (
    generate_magic_code, store_magic_code, verify_magic_code as redis_verify_magic_code,
    MAGIC_CODE_EXPIRY_SECONDS,
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
    user = get_user_by_email(db, body.email)

    if directory_service.is_configured():
        user = _resolve_against_directory(db, body.email, user)

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


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user or user.status == UserStatus.deactivated:
        raise HTTPException(status_code=401, detail="User not found")
    if payload.get("ver", 1) != user.token_version:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
        needs_password=user.password_hash is None,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


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
