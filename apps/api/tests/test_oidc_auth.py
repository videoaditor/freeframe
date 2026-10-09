"""Central-gate OIDC: pure unit tests for apps/api/services/oidc_auth.py.

No network or DB - `_discovery`/`_jwks` are patched directly, and the id_tokens
are signed with a real, locally generated RSA key so `verify_id_token` runs
its actual signature-verification code path (python-jose + cryptography),
not a mock of it.
"""
import base64
import hashlib
import time
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk as jose_jwk
from jose import jwt as jose_jwt

from apps.api.services import oidc_auth

ISSUER = "https://auth.aditor.ai"
CLIENT_ID = "freeframe-web"
KID = "gate-test-kid"


def _rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


_PRIVATE_PEM, _PUBLIC_PEM = _rsa_keypair()
_JWK = jose_jwk.construct(_PUBLIC_PEM, algorithm="RS256").to_dict()
_JWK["kid"] = KID


ACCESS_TOKEN = "the-access-token"


def _id_token(*, access_token=None, **claim_overrides):
    """A gate id_token. `access_token`, when given, makes jose compute and embed
    a real `at_hash` claim (exactly like the gate does), so tests can exercise
    the actual at_hash-verification code path rather than a token that simply
    omits the claim."""
    claims = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "exp": time.time() + 300,
        "email": "max@aditor.ai",
        "nonce": "the-nonce",
    }
    claims.update(claim_overrides)
    return jose_jwt.encode(
        claims, _PRIVATE_PEM, algorithm="RS256", headers={"kid": KID}, access_token=access_token,
    )


@pytest.fixture(autouse=True)
def _oidc_configured():
    with patch.object(oidc_auth.settings, "oidc_issuer", ISSUER), \
         patch.object(oidc_auth.settings, "oidc_client_id", CLIENT_ID), \
         patch.object(oidc_auth.settings, "oidc_client_secret", "shh"), \
         patch.object(oidc_auth.settings, "oidc_scope", "freeframe.read"):
        yield


@pytest.fixture(autouse=True)
def _clear_caches():
    oidc_auth._discovery_cache.clear()
    oidc_auth._jwks_cache.clear()
    yield
    oidc_auth._discovery_cache.clear()
    oidc_auth._jwks_cache.clear()


@pytest.fixture
def jwks_mocked():
    with patch.object(oidc_auth, "_discovery", return_value={
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/jwks",
        "end_session_endpoint": f"{ISSUER}/endsession",
    }), patch.object(oidc_auth, "_jwks", return_value=[_JWK]):
        yield


# ── oidc_enabled / full_scope ─────────────────────────────────────────────

def test_oidc_enabled_requires_all_three():
    assert oidc_auth.oidc_enabled() is True
    with patch.object(oidc_auth.settings, "oidc_client_secret", ""):
        assert oidc_auth.oidc_enabled() is False


def test_full_scope_appends_configured_extra():
    assert oidc_auth.full_scope() == "openid profile email offline_access freeframe.read"
    with patch.object(oidc_auth.settings, "oidc_scope", ""):
        assert oidc_auth.full_scope() == "openid profile email offline_access"


# ── PKCE ───────────────────────────────────────────────────────────────────

def test_new_pkce_pair_challenge_matches_verifier():
    verifier, challenge = oidc_auth.new_pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
    assert challenge == expected
    assert "=" not in challenge
    # Two calls never reuse a verifier.
    verifier2, _ = oidc_auth.new_pkce_pair()
    assert verifier != verifier2


# ── authorize_url ────────────────────────────────────────────────────────

def test_authorize_url_carries_pkce_and_resource(jwks_mocked):
    url = oidc_auth.authorize_url(
        redirect_uri="https://feedback.aditor.ai/api/auth/oidc/callback",
        state="s1", nonce="n1", code_challenge="c1", resource="https://feedback.aditor.ai",
    )
    assert url.startswith(f"{ISSUER}/authorize?")
    for fragment in (
        "response_type=code", "client_id=freeframe-web", "state=s1", "nonce=n1",
        "code_challenge=c1", "code_challenge_method=S256",
        "resource=https%3A%2F%2Ffeedback.aditor.ai",
        "redirect_uri=https%3A%2F%2Ffeedback.aditor.ai%2Fapi%2Fauth%2Foidc%2Fcallback",
    ):
        assert fragment in url


# ── exchange_code ────────────────────────────────────────────────────────

def test_exchange_code_uses_client_secret_basic(jwks_mocked):
    captured = {}

    class _Resp:
        status_code = 200
        def json(self):
            return {"id_token": "abc"}

    def _fake_post(url, timeout, data, auth):
        captured.update(url=url, data=data, auth=auth)
        return _Resp()

    with patch("apps.api.services.oidc_auth.httpx.post", side_effect=_fake_post):
        result = oidc_auth.exchange_code(code="c", redirect_uri="https://x/callback", code_verifier="v")

    assert result == {"id_token": "abc"}
    assert captured["url"] == f"{ISSUER}/token"
    assert captured["auth"] == (CLIENT_ID, "shh")
    assert captured["data"]["code"] == "c"
    assert captured["data"]["code_verifier"] == "v"
    assert captured["data"]["grant_type"] == "authorization_code"


def test_exchange_code_raises_on_non_200(jwks_mocked):
    class _Resp:
        status_code = 400
        def json(self):
            return {}

    with patch("apps.api.services.oidc_auth.httpx.post", return_value=_Resp()):
        with pytest.raises(oidc_auth.OIDCError):
            oidc_auth.exchange_code(code="c", redirect_uri="https://x/callback", code_verifier="v")


# ── verify_id_token ──────────────────────────────────────────────────────

def test_verify_id_token_accepts_a_good_token(jwks_mocked):
    claims = oidc_auth.verify_id_token(_id_token(), nonce="the-nonce", access_token=ACCESS_TOKEN)
    assert claims["email"] == "max@aditor.ai"


def test_verify_id_token_accepts_a_good_token_with_at_hash(jwks_mocked):
    """The gate's real id_token always carries at_hash - exercise that actual
    verification path (not just a token that happens to omit the claim)."""
    token = _id_token(access_token=ACCESS_TOKEN)
    claims = oidc_auth.verify_id_token(token, nonce="the-nonce", access_token=ACCESS_TOKEN)
    assert claims["email"] == "max@aditor.ai"


def test_verify_id_token_rejects_at_hash_mismatch(jwks_mocked):
    token = _id_token(access_token=ACCESS_TOKEN)
    with pytest.raises(oidc_auth.OIDCError):
        oidc_auth.verify_id_token(token, nonce="the-nonce", access_token="a-different-access-token")


def test_verify_id_token_rejects_tampered_signature(jwks_mocked):
    token = _id_token()
    head, payload, sig = token.split(".")
    tampered = f"{head}.{payload}.{sig[:-4]}{'A' * 4}"
    with pytest.raises(oidc_auth.OIDCError):
        oidc_auth.verify_id_token(tampered, nonce="the-nonce", access_token=ACCESS_TOKEN)


def test_verify_id_token_rejects_expired_token(jwks_mocked):
    token = _id_token(exp=time.time() - 60)
    with pytest.raises(oidc_auth.OIDCError):
        oidc_auth.verify_id_token(token, nonce="the-nonce", access_token=ACCESS_TOKEN)


def test_verify_id_token_rejects_wrong_audience(jwks_mocked):
    token = _id_token(aud="someone-else")
    with pytest.raises(oidc_auth.OIDCError):
        oidc_auth.verify_id_token(token, nonce="the-nonce", access_token=ACCESS_TOKEN)


def test_verify_id_token_rejects_wrong_issuer(jwks_mocked):
    token = _id_token(iss="https://evil.example")
    with pytest.raises(oidc_auth.OIDCError):
        oidc_auth.verify_id_token(token, nonce="the-nonce", access_token=ACCESS_TOKEN)


def test_verify_id_token_rejects_nonce_mismatch(jwks_mocked):
    token = _id_token()
    with pytest.raises(oidc_auth.OIDCError):
        oidc_auth.verify_id_token(token, nonce="not-the-nonce", access_token=ACCESS_TOKEN)


def test_verify_id_token_rejects_missing_email(jwks_mocked):
    token = _id_token(email=None)
    with pytest.raises(oidc_auth.OIDCError):
        oidc_auth.verify_id_token(token, nonce="the-nonce", access_token=ACCESS_TOKEN)


def test_verify_id_token_rejects_non_rs256_algorithm(jwks_mocked):
    """The verification algorithm is pinned to RS256 server-side, never read
    from the token's own `alg` header - the standard mitigation for JWT "alg
    confusion" attacks (e.g. a token that declares HS256 and is signed with
    key material an attacker hopes the verifier reuses as an HMAC secret).
    Rejected before the JWKS/kid lookup even runs, for any alg but RS256."""
    claims = {"iss": ISSUER, "aud": CLIENT_ID, "exp": time.time() + 300,
              "email": "max@aditor.ai", "nonce": "the-nonce"}
    token = jose_jwt.encode(claims, "arbitrary-shared-secret", algorithm="HS256", headers={"kid": KID})
    with pytest.raises(oidc_auth.OIDCError, match="unsupported algorithm"):
        oidc_auth.verify_id_token(token, nonce="the-nonce", access_token=ACCESS_TOKEN)


def test_verify_id_token_rejects_unknown_signing_key(jwks_mocked):
    other_private, _ = _rsa_keypair()
    token = jose_jwt.encode(
        {"iss": ISSUER, "aud": CLIENT_ID, "exp": time.time() + 300, "email": "x@y.com", "nonce": "the-nonce"},
        other_private, algorithm="RS256", headers={"kid": "not-in-jwks"},
    )
    with pytest.raises(oidc_auth.OIDCError):
        oidc_auth.verify_id_token(token, nonce="the-nonce", access_token=ACCESS_TOKEN)


# ── end_session_url ──────────────────────────────────────────────────────

def test_end_session_url_carries_id_token_hint(jwks_mocked):
    url = oidc_auth.end_session_url(
        post_logout_redirect_uri=f"{ISSUER}/signed-out", id_token_hint="idt",
    )
    assert url.startswith(f"{ISSUER}/endsession?")
    assert "id_token_hint=idt" in url
    assert "post_logout_redirect_uri=https%3A%2F%2Fauth.aditor.ai%2Fsigned-out" in url


def test_end_session_url_omits_hint_when_absent(jwks_mocked):
    url = oidc_auth.end_session_url(post_logout_redirect_uri=f"{ISSUER}/signed-out", id_token_hint=None)
    assert "id_token_hint" not in url


def test_end_session_url_falls_back_to_login_when_discovery_lacks_it():
    with patch.object(oidc_auth, "_discovery", return_value={"authorization_endpoint": "x", "token_endpoint": "y", "jwks_uri": "z"}), \
         patch.object(oidc_auth.settings, "frontend_url", "https://feedback.aditor.ai"):
        url = oidc_auth.end_session_url(post_logout_redirect_uri="whatever", id_token_hint=None)
    assert url == "https://feedback.aditor.ai/login"


def test_signed_out_redirect_uri_derives_from_issuer():
    assert oidc_auth.signed_out_redirect_uri() == f"{ISSUER}/signed-out"
