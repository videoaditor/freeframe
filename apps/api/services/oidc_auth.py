"""Central-gate (auth.aditor.ai) OIDC sign-in, terminated in this API.

Option B from spec #65: the gate issues an id_token which this service verifies
against the gate's JWKS, then the router mints FreeFrame's own existing HS256
session tokens (auth_service.create_access_token/create_refresh_token) exactly
as a password sign-in already does. No gate token is ever stored
long-term or handed to the browser - only the id_token, briefly, to resolve who
signed in.

Discovery and JWKS documents are cached in-process; both are public, signed-
key-rotation-tolerant documents meant to be fetched occasionally, not once per
login.
"""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
from jose import jwt as jose_jwt
from jose.exceptions import JWTError

from ..config import settings

_CACHE_TTL_SECONDS = 3600
_discovery_cache: dict = {}
_jwks_cache: dict = {}

STANDARD_SCOPES = "openid profile email offline_access"
JWT_ALGORITHM = "RS256"


class OIDCError(Exception):
    """Any failure in the gate handshake - deliberately one type.

    The router turns every one of these into the same generic redirect, so
    the gate's own error detail is never shown to (or distinguishable by) the
    browser.
    """


def oidc_enabled() -> bool:
    return bool(settings.oidc_issuer and settings.oidc_client_id and settings.oidc_client_secret)


def full_scope() -> str:
    extra = settings.oidc_scope.strip()
    return f"{STANDARD_SCOPES} {extra}" if extra else STANDARD_SCOPES


def new_pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) per RFC 7636 - S256 only."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _get_json(url: str) -> dict:
    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OIDCError(f"could not fetch {url}") from exc


def _discovery(*, force: bool = False) -> dict:
    now = time.time()
    if not force and _discovery_cache.get("doc") and _discovery_cache.get("at", 0) + _CACHE_TTL_SECONDS > now:
        return _discovery_cache["doc"]
    doc = _get_json(f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration")
    _discovery_cache["doc"] = doc
    _discovery_cache["at"] = now
    return doc


def _jwks(*, force: bool = False) -> list[dict]:
    now = time.time()
    if not force and _jwks_cache.get("keys") is not None and _jwks_cache.get("at", 0) + _CACHE_TTL_SECONDS > now:
        return _jwks_cache["keys"]
    keys = _get_json(_discovery()["jwks_uri"]).get("keys", [])
    _jwks_cache["keys"] = keys
    _jwks_cache["at"] = now
    return keys


def authorize_url(*, redirect_uri: str, state: str, nonce: str, code_challenge: str, resource: str) -> str:
    doc = _discovery()
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": redirect_uri,
        "scope": full_scope(),
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "resource": resource,
    }
    return f"{doc['authorization_endpoint']}?{urlencode(params)}"


def exchange_code(*, code: str, redirect_uri: str, code_verifier: str) -> dict:
    """Trade the authorization code for tokens via client_secret_basic."""
    doc = _discovery()
    try:
        response = httpx.post(
            doc["token_endpoint"],
            timeout=10,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            auth=(settings.oidc_client_id, settings.oidc_client_secret),
        )
    except httpx.HTTPError as exc:
        raise OIDCError("gate token exchange request failed") from exc
    if response.status_code != 200:
        raise OIDCError(f"gate token exchange returned {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise OIDCError("gate token exchange returned a non-JSON body") from exc


def verify_id_token(id_token: str, *, nonce: str, access_token: str | None) -> dict:
    """Verify signature (against the gate's JWKS), issuer, audience, expiry,
    nonce and (when the token carries one) at_hash. Returns the claims on
    success; raises OIDCError on any mismatch, including a tampered signature
    or an expired token.

    `access_token` is required to check `at_hash`: the gate's id_token always
    carries that claim, and python-jose raises JWTClaimsError if it's asked to
    verify at_hash without the access_token to hash and compare against.
    """
    try:
        header = jose_jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise OIDCError("malformed id_token") from exc

    # Pin the algorithm ourselves rather than trusting the token's own `alg`
    # header - deciding the verification algorithm from attacker-controlled
    # input is the classic JWT "alg confusion" hole (e.g. a token claiming
    # HS256 and signing with an RSA public key's modulus as the HMAC secret).
    # The gate's JWKS only ever publishes RSA keys, so RS256 is the only
    # algorithm that can be legitimate here.
    if header.get("alg") != JWT_ALGORITHM:
        raise OIDCError(f"id_token uses an unsupported algorithm: {header.get('alg')!r}")

    kid = header.get("kid")
    keys = _jwks()
    key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        # The gate may have rotated signing keys since our cache was filled.
        keys = _jwks(force=True)
        key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        raise OIDCError("id_token signed by an unknown key")

    try:
        claims = jose_jwt.decode(
            id_token,
            key,
            algorithms=[JWT_ALGORITHM],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer,
            access_token=access_token,
        )
    except JWTError as exc:
        raise OIDCError("id_token failed verification") from exc

    if claims.get("nonce") != nonce:
        raise OIDCError("id_token nonce mismatch")

    email = claims.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise OIDCError("id_token has no usable email claim")

    return claims


def end_session_url(*, post_logout_redirect_uri: str, id_token_hint: str | None) -> str:
    """The gate's RP-initiated logout URL, or a plain `/login` fallback.

    Discovery not answering `end_session_endpoint` is treated the same as OIDC
    being unconfigured: sign-out must never get stuck because the gate's own
    metadata is incomplete.
    """
    try:
        endpoint = _discovery().get("end_session_endpoint")
    except OIDCError:
        endpoint = None
    if not endpoint:
        return f"{settings.frontend_url.rstrip('/')}/login"
    params = {"post_logout_redirect_uri": post_logout_redirect_uri}
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    return f"{endpoint}?{urlencode(params)}"


def signed_out_redirect_uri() -> str:
    return f"{settings.oidc_issuer.rstrip('/')}/signed-out"
