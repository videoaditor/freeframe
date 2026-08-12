from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from ..database import get_db
import secrets as _secrets

from ..services.auth_service import decode_token, get_user_by_id, get_user_by_email
from ..models.user import User, UserStatus
from ..config import settings

bearer_scheme = HTTPBearer(auto_error=False)
optional_bearer_scheme = HTTPBearer(auto_error=False)

def _service_key_user(request: Request, db: Session) -> Optional[User]:
    """Resolve a read-only service principal from the X-API-Key header.

    Returns None when the mechanism is unconfigured or the header is absent, so
    the caller falls through to normal bearer auth.
    """
    configured = settings.service_api_key
    if not configured or not settings.service_api_key_email:
        return None
    presented = request.headers.get("x-api-key")
    if not presented:
        return None
    # Constant time: a plain == leaks the shared secret one byte at a time.
    if not _secrets.compare_digest(presented, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    if request.method != "GET":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key is read-only",
        )
    user = get_user_by_email(db, settings.service_api_key_email)
    if not user or user.status == UserStatus.deactivated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Service account unavailable")
    return user


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    service_user = _service_key_user(request, db)
    if service_user:
        return service_user
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user or user.status == UserStatus.deactivated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")
    return user

def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns the authenticated user if a valid token is provided, None otherwise."""
    try:
        service_user = _service_key_user(request, db)
    except HTTPException:
        # On the optional path a bad key is simply "not authenticated" - these
        # endpoints are reachable by anonymous guests via share links.
        return None
    if service_user:
        return service_user
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if not payload or payload.get("type") != "access":
            return None
        user = get_user_by_id(db, uuid.UUID(payload["sub"]))
        if not user or user.status == UserStatus.deactivated:
            return None
        return user
    except Exception:
        return None

