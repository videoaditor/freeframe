"""Google sign-in: trade an OAuth code for a Google-verified email.

The id_token comes straight from Google's token endpoint over HTTPS, authenticated with our
client secret, so its signature does not need a JWKS check (Google OIDC docs, "Obtain user
information from the ID token"). We still check audience, issuer, expiry and email_verified.
Nothing from Google is stored: the verified email is the identity, exactly like a magic code.
"""
import time

import httpx
from fastapi import HTTPException
from jose import JWTError, jwt

from ..config import settings

TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


def google_enabled() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def verified_email(claims: dict, client_id: str, now: float | None = None) -> str | None:
    """The email Google vouches for, or None if these claims are not for us / not verified."""
    aud = claims.get("aud")
    if (aud if isinstance(aud, list) else [aud]).count(client_id) == 0:
        return None
    if claims.get("iss") not in ISSUERS:
        return None
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)) or exp <= (now if now is not None else time.time()):
        return None
    if claims.get("email_verified") not in (True, "true"):
        return None
    email = claims.get("email")
    return email.strip() if isinstance(email, str) and "@" in email else None


def email_from_code(code: str, redirect_uri: str) -> str:
    """Exchange the code; any failure is the same generic 401."""
    fail = HTTPException(401, "Google sign-in failed. Please try again.")
    try:
        r = httpx.post(TOKEN_URL, timeout=10, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        if r.status_code != 200:
            raise fail
        claims = jwt.get_unverified_claims(r.json()["id_token"])
    except (httpx.HTTPError, KeyError, ValueError, JWTError):
        raise fail from None
    email = verified_email(claims, settings.google_client_id)
    if not email:
        raise fail
    return email
