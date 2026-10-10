"""Outbound events to the hub when a client asks for changes or an editor answers.

Replaces the n8n `freeframe-comment-ping`: FreeFrame stays "dumb" here. It only tells the hub
`client_comment` (a guest reviewer commented on a hand-in version) or `revision_submitted` (a new
version landed through the hand-in lane) - the hub decides what to do about it (ping, escalate,
Trust). Modelled on `automation_share.py`: off by default, fired after commit, best effort, never
fails the request that triggered it.
"""

import hashlib
import hmac
import json
import logging
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models.upload_request import UploadRequest

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return bool((getattr(settings, "hub_events_webhook_url", "") or "").strip())


def _handin_request_for_asset(db: Session, asset) -> Optional[UploadRequest]:
    """The hand-in request this asset's folder belongs to, with a card to report against - None for
    a plain upload/comment that is not part of a hand-in (a staff hand-in folder holds at most one
    request, enforced in routers/requests.py `folder_editor_request`)."""
    if asset is None or getattr(asset, "folder_id", None) is None:
        return None
    req = db.query(UploadRequest).filter(UploadRequest.folder_id == asset.folder_id).first()
    if req is None:
        return None
    state = req.iteration_state if isinstance(req.iteration_state, dict) else {}
    internal = state.get("internal_handin")
    if not isinstance(internal, dict) or not (internal.get("card_url") or "").strip():
        return None
    return req


def _post(event: dict) -> None:
    url = (getattr(settings, "hub_events_webhook_url", "") or "").strip()
    if not url:
        return
    secret = (getattr(settings, "hub_events_webhook_secret", "") or "").strip()
    body = json.dumps(event).encode("utf-8")
    headers = {"content-type": "application/json"}
    if secret:
        headers["X-Aditor-Signature"] = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    try:
        httpx.post(url, content=body, headers=headers, timeout=10)
    except Exception:  # noqa: BLE001 - a webhook must never fail the comment/upload it reports
        logger.warning("hub events webhook failed for event %r", event.get("event"), exc_info=True)


def announce_client_comment(db: Session, comment, asset, author_name: Optional[str]) -> None:
    """A guest-reviewer comment on a hand-in version. Never fires for a team comment (`author_id`
    set, `guest_author_id` None) or an auto-review finding (stored `visibility="internal"` at write
    time by `_guest_comment_visibility` / `publish_review_comment` - see routers/comments.py)."""
    if not is_enabled():
        return
    if comment.guest_author_id is None or getattr(comment, "visibility", "public") == "internal":
        return
    req = _handin_request_for_asset(db, asset)
    if req is None:
        return
    internal = req.iteration_state["internal_handin"]
    _post({
        "event": "client_comment",
        "card_url": internal.get("card_url"),
        "editor_email": req.last_uploader_email,
        "comment": {"id": str(comment.id), "body": comment.body, "author_name": author_name},
        "version_id": str(comment.version_id),
    })


def announce_revision_submitted(db: Session, asset, version_id) -> None:
    """A new version completed via the hand-in lane (routers/upload.py `complete`)."""
    if not is_enabled():
        return
    req = _handin_request_for_asset(db, asset)
    if req is None:
        return
    internal = req.iteration_state["internal_handin"]
    _post({
        "event": "revision_submitted",
        "card_url": internal.get("card_url"),
        "editor_email": req.last_uploader_email,
        "version_id": str(version_id),
    })
