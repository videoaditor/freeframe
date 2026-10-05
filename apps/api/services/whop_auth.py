"""Whop owner → isolated customer, using the Suite's verified owner exchange.

The owner JWT is obtained only over HTTPS from the configured Suite (never from
browser input). Suite verifies its signature during entitlement checks. Redis
keeps that credential server-side until its own expiry; FreeFrame tokens cannot
extend it. Existing accounts are never linked merely by matching an email.
"""
from dataclasses import dataclass, replace
import time
import uuid

import httpx
from fastapi import HTTPException
from jose import JWTError, jwt
from pydantic import EmailStr, TypeAdapter, ValidationError
from redis.exceptions import RedisError
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models.user import User, UserStatus
from .redis_service import get_redis
from . import campaign_access


@dataclass(frozen=True)
class Owner:
    token: str
    account_id: str
    brand_id: str
    email: str
    expires: int
    campaign: dict | None = None


def _suite_url() -> str:
    url = settings.suite_url.rstrip('/')
    if not url.startswith('https://') or not settings.whop_app_id:
        raise HTTPException(503, 'Whop sign-in is not configured yet')
    return url


def _claims(token: str, audience: str) -> dict:
    # Only a rejection preflight, NOT signature verification. Whop verification
    # happens in Suite; owner signature verification happens at entitlement/check.
    try:
        claims = jwt.get_unverified_claims(token)
        audiences = claims.get('aud')
        if isinstance(audiences, str):
            audiences = [audiences]
        expires = claims.get('exp')
        if not isinstance(expires, int) or expires <= time.time() or audience not in (audiences or []):
            raise ValueError()
        return claims
    except (JWTError, ValueError, TypeError):
        raise HTTPException(401, 'Open Aditor Review again from Whop') from None


def owner_from_token(token: str) -> Owner:
    """Read a token from our HTTPS exchange or private Redis, never a request body."""
    claims = _claims(token, 'aditor-suite:owner')
    account, brand = claims.get('accountId'), claims.get('brandId')
    if not all(isinstance(v, str) and 0 < len(v) <= 255 for v in (account, brand)):
        raise HTTPException(401, 'Whop identity is incomplete')
    try:
        email = str(TypeAdapter(EmailStr).validate_python(claims.get('email'))).lower()
    except ValidationError:
        raise HTTPException(401, 'Whop identity is incomplete') from None
    return Owner(token, account, brand, email, claims['exp'])


def _post(path: str, **kwargs) -> dict:
    try:
        response = httpx.post(f'{_suite_url()}{path}', timeout=10, follow_redirects=False, **kwargs)
        if response.status_code in (401, 403):
            raise HTTPException(401, 'Open Aditor Review again from Whop')
        if not response.is_success:
            raise HTTPException(503, 'Whop access could not be checked. Try again shortly.')
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'Whop access could not be checked. Try again shortly.') from None


def check_entitlement(owner_token: str, *, allow_expired: bool = False) -> dict:
    data = _post('/v1/entitlement/check', headers={'Authorization': f'Bearer {owner_token}'},
                 json={'tool': 'autoreview'})
    campaign = campaign_access.validate_context(data.get('campaign'))
    ended = bool(campaign and campaign['previewOnly'] and campaign['state'] == 'expired')
    if ended and (data.get('allow') is True or data.get('reason') == 'campaign_expired'):
        if not allow_expired:
            raise campaign_access.expired_error()
    elif data.get('allow') is not True:
        raise HTTPException(403, 'Your Whop membership does not currently include Aditor Review')
    return {**data, 'campaign': campaign}


def exchange_whop_token(whop_token: str) -> Owner:
    _suite_url()
    if not whop_token or len(whop_token) > 16384:
        raise HTTPException(401, 'Open Aditor Review from Whop to sign in')
    _claims(whop_token, settings.whop_app_id)
    data = _post('/v1/auth/owner', headers={'x-whop-user-token': whop_token, 'x-suite-app': 'review'}, json={})
    if not isinstance(data.get('token'), str):
        raise HTTPException(503, 'Whop sign-in returned an incomplete response')
    owner = owner_from_token(data['token'])
    entitlement = check_entitlement(owner.token, allow_expired=True)
    return replace(owner, campaign=entitlement.get('campaign'))


def _matches(user: User, owner: Owner) -> bool:
    return (user.suite_account_id == owner.account_id and user.suite_brand_id == owner.brand_id
            and user.is_staff is False and user.is_superadmin is False
            and user.status == UserStatus.active and user.deleted_at is None)


def resolve_customer(db: Session, owner: Owner) -> User:
    # Include tombstones ONLY to reject reuse; a deleted identity must not silently
    # acquire a fresh workspace. Unique constraints also reserve tombstoned keys.
    user = db.query(User).filter(or_(User.suite_account_id == owner.account_id,
                                     User.suite_brand_id == owner.brand_id)).first()
    if user:
        if not _matches(user, owner):
            raise HTTPException(403, 'This Whop account needs an account review. Contact support.')
        campaign_access.save_context(user, owner.campaign)
        return user
    if db.query(User).filter(func.lower(User.email) == owner.email).first():
        raise HTTPException(409, 'This email already has an account. Contact support to connect it to Whop.')
    user = User(id=uuid.uuid4(), email=owner.email, name='Owner', password_hash=None,
                status=UserStatus.active, is_staff=False, is_superadmin=False,
                email_verified=False, preferences={}, token_version=1,
                suite_account_id=owner.account_id, suite_brand_id=owner.brand_id,
                suite_campaign=owner.campaign)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Sign-in was already started. Try again.') from None
    return user


def session_key(user_id) -> str:
    return f'whop:owner:{user_id}'


def gate_key(user_id) -> str:
    return f'whop:gate:{user_id}'


def store_owner_session(user: User, owner: Owner) -> None:
    try:
        redis = get_redis()
        redis.setex(session_key(user.id), max(1, owner.expires - int(time.time())), owner.token)
        redis.delete(gate_key(user.id))
    except RedisError:
        raise HTTPException(503, 'Sign-in is temporarily unavailable. Try again shortly.') from None


def require_customer_entitlement(user: User, *, allow_expired: bool = False) -> None:
    # Plain users (including pre-existing staff) keep their existing auth contract.
    if not isinstance(user.suite_account_id, str) or not user.suite_account_id:
        return
    _suite_url()
    try:
        redis = get_redis()
        token = redis.get(session_key(user.id))
        if not token:
            raise HTTPException(401, 'Open Aditor Review again from Whop')
        owner = owner_from_token(token)
        if not _matches(user, owner):
            raise HTTPException(401, 'Whop session does not match this account')
        if redis.get(gate_key(user.id)) == token and not campaign_access.preview_expired(user):
            return
        # At most 60 seconds of revocation delay. No fresh access is granted on an
        # outage; an already verified cached decision survives only its normal TTL.
        entitlement = check_entitlement(token, allow_expired=allow_expired)
        campaign_access.save_context(user, entitlement.get('campaign'))
        if campaign_access.preview_expired(user):
            return  # Identity-only allowance is never cached as a tool-access grant.
        redis.setex(gate_key(user.id), min(60, max(1, owner.expires - int(time.time()))), token)
    except RedisError:
        raise HTTPException(503, 'Whop access could not be checked. Try again shortly.') from None


def require_current_campaign_paid_access(user: User) -> None:
    """Revalidate a saved paid override for guest links after campaign expiry.

    The caller can hold upload row locks: do not mutate user context or commit.
    Suite owns paid-membership freshness; the local persisted flag is not a grant.
    """
    try:
        token = get_redis().get(session_key(user.id))
        if not token:
            raise HTTPException(401, 'Open Aditor Review again from Whop')
        owner = owner_from_token(token)
        if not _matches(user, owner):
            raise HTTPException(401, 'Whop session does not match this account')
        entitlement = check_entitlement(token)
        campaign = entitlement.get('campaign')
        if not campaign:
            raise HTTPException(503, 'Trial access could not be verified. Try again shortly.')
        if campaign['previewOnly']:
            raise campaign_access.expired_error()
    except RedisError:
        raise HTTPException(503, 'Whop access could not be checked. Try again shortly.') from None
