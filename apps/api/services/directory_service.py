"""Look up a sign-in address in an external people directory.

Instances whose roster already lives somewhere else - an HR table, a company
database, an internal API - can point ``DIRECTORY_LOOKUP_URL`` at it instead of
maintaining a second copy of their people here. The magic-code endpoint then
treats that directory as the authority on who may sign in: a listed person is
provisioned on first sign-in, and a person the directory no longer lists as
active is refused.

The directory is only ever read, never written, and the lookup is deliberately
narrow: one GET, one short timeout, no retries. It sits in the sign-in path, so
a slow directory must not become a slow login.

Unset ``DIRECTORY_LOOKUP_URL`` (the default) disables all of this.
"""

import logging
from urllib.parse import quote

import httpx

try:
    from ..config import settings
except ImportError:  # pragma: no cover - direct-module import in some tooling
    from config import settings

logger = logging.getLogger(__name__)


class DirectoryUnavailable(Exception):
    """The directory could not be reached, or answered in a shape we can't read.

    Deliberately distinct from "this person is not listed": callers must be able
    to tell an outage from an answer, because the two warrant opposite
    decisions.
    """


def is_configured() -> bool:
    return bool(settings.directory_lookup_url)


def find_person(email: str) -> dict | None:
    """Return the directory record for ``email``, or None if it lists nobody.

    Raises DirectoryUnavailable if the directory could not be consulted.
    """
    url = settings.directory_lookup_url
    if not url:
        return None

    headers = {"Accept": "application/json"}
    if settings.directory_token:
        headers["Authorization"] = f"Bearer {settings.directory_token}"

    try:
        response = httpx.get(
            url.replace("{email}", quote(email, safe="")),
            headers=headers,
            timeout=settings.directory_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        # Never leak the address into logs on the failure path; the point of the
        # lookup is that unknown addresses stay unremarkable.
        logger.warning("People directory lookup failed: %s", exc)
        raise DirectoryUnavailable(str(exc)) from exc

    # A collection endpoint answers with a list, a single-record endpoint with
    # an object. Accept both so this works against more than one directory.
    if isinstance(payload, list):
        record = payload[0] if payload else None
    elif isinstance(payload, dict):
        record = payload or None
    else:
        raise DirectoryUnavailable(f"unexpected payload type {type(payload).__name__}")

    return record


def allowed_statuses() -> set[str]:
    return {
        s.strip().lower()
        for s in (settings.directory_allowed_statuses or "").split(",")
        if s.strip()
    }


def is_allowed(record: dict) -> bool:
    """Whether a directory record describes someone currently allowed to sign in.

    Deliberately a set rather than an equality check. Rosters tend to carry more
    than one working state - between assignments, onboarding, on leave - and only
    the states that mean *gone* should cost someone their access.
    """
    field = settings.directory_status_field
    allowed = allowed_statuses()
    if not field or not allowed:
        # A directory with no notion of status vouches for everyone it lists.
        return True
    return str(record.get(field, "")).lower() in allowed


def display_name(record: dict, fallback: str) -> str:
    name = record.get(settings.directory_name_field)
    return str(name).strip() if name and str(name).strip() else fallback
