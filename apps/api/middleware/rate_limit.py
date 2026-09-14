"""
IP-based rate limiting dependency for FastAPI routes.

Usage:
    @router.post("/endpoint", dependencies=[Depends(rate_limit("action", 5, 60))])
    def my_endpoint(): ...

This limits to 5 requests per 60 seconds per IP for "action".
"""

import secrets as _secrets

from fastapi import HTTPException, Request, status
from ..config import settings
from ..services.redis_service import check_rate_limit


def is_trusted_service_request(request: Request) -> bool:
    """True when the request carries the valid service API key.

    Trusted internal traffic - above all the automated reviewer fetching shares to review - bypasses
    the public IP limiter. The reviewer comes from ONE egress IP but resolves many DISTINCT valid
    share tokens in a burst (a batch hand-in of 10 videos), which the per-IP `share_validate` limiter
    reads as token brute force and 429s. That is exactly the "share-unreachable 429 - FreeFrame is
    rate-limiting us" that stopped Auto Review from checking batch hand-ins. A real anonymous client
    presents no key and is still limited, so the abuse ceiling is unchanged.
    """
    configured = settings.service_api_key
    presented = request.headers.get("x-api-key")
    return bool(configured and presented and _secrets.compare_digest(presented, configured))


def rate_limit(action: str, max_requests: int, window_seconds: int):
    """
    Returns a FastAPI dependency that enforces IP-based rate limiting.

    Args:
        action: Unique key for this rate limit (e.g. "send_magic_code")
        max_requests: Maximum requests allowed in the window
        window_seconds: Time window in seconds
    """

    def _dependency(request: Request):
        if is_trusted_service_request(request):
            return
        # Use X-Real-Ip (set by trusted reverse proxy like Traefik) or fall back to ASGI client IP
        # Do NOT use X-Forwarded-For as it can be spoofed by the client
        ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")

        allowed, retry_after = check_rate_limit(ip, action, max_requests, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return _dependency
