"""Outbound events to the hub when a client asks for changes or an editor answers.

Replaces the n8n `freeframe-comment-ping`: FreeFrame stays "dumb" here. It only tells the hub
`client_comment` (a guest reviewer commented on a video) or `revision_submitted` (a new version
landed) - the hub decides what to do about it (ping, escalate, Trust). Modelled on
`automation_share.py`: off by default, fired after commit, best effort, never fails the request that
triggered it.

Delivery path must not matter: a client comment on ANY asset routes to its responsible editor, not
only assets that came through the internal hand-in lane. Each event is keyed on the asset's own
FreeFrame page; a hand-in card (when there is one) is kept as enrichment and as the submit link.
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


def _review_url(req) -> Optional[str]:
    """The editor-facing review link for a hand-in request - same /r/<token> link the
    editor-submissions list uses. None if the request has no token (can't resolve), in which case
    the caller falls back to the asset page rather than blocking the event."""
    token = getattr(req, "token", None)
    if not token:
        return None
    base = (getattr(settings, "frontend_url", "") or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/r/{token}"


def _asset_page_url(asset) -> Optional[str]:
    """The FreeFrame asset page - where the editor reads the client's comments and uploads the new
    version. It is the stable per-asset key a non-hand-in revision is tracked and resolved on, so
    the comment event and the later revision_submitted event compute the SAME url for an asset."""
    base = (getattr(settings, "frontend_url", "") or "").strip().rstrip("/")
    project_id = getattr(asset, "project_id", None)
    asset_id = getattr(asset, "id", None)
    if not base or not project_id or not asset_id:
        return None
    return f"{base}/projects/{project_id}/assets/{asset_id}"


def _user_email(db: Session, user_id) -> Optional[str]:
    if not user_id:
        return None
    try:
        from ..models.user import User
        user = db.get(User, user_id)
        email = (getattr(user, "email", None) or "").strip()
        return email or None
    except Exception:  # noqa: BLE001 - resolution is best effort; a miss just skips the event
        return None


def _project_name(db: Session, project_id) -> Optional[str]:
    if not project_id:
        return None
    try:
        from ..models.project import Project
        project = db.get(Project, project_id)
        return (getattr(project, "name", None) or None)
    except Exception:  # noqa: BLE001
        return None


def _responsible_editor_email(db: Session, asset, version_id) -> Optional[str]:
    """The editor who owns the fix: whoever uploaded the version in question, else whoever created
    the asset. Mirrors billing's `Asset.created_by` = editor convention, but prefers the specific
    version the client commented on when we have it."""
    uploader_id = None
    if version_id is not None:
        try:
            from ..models.asset import AssetVersion
            version = db.get(AssetVersion, version_id)
            uploader_id = getattr(version, "created_by", None)
        except Exception:  # noqa: BLE001
            uploader_id = None
    if not uploader_id:
        uploader_id = getattr(asset, "created_by", None)
    return _user_email(db, uploader_id)


def _asset_report_context(db: Session, asset, version_id) -> Optional[dict]:
    """Resolve who to tell and where to point them for an asset event, or None when no editor can be
    resolved (then the caller stays silent, never errors). Hand-in assets keep the hand-in card and
    /r/<token> review link; every other asset is keyed on its own FreeFrame page and routed to the
    version's uploader."""
    if asset is None:
        return None
    req = _handin_request_for_asset(db, asset)
    title = getattr(asset, "name", None) or None
    client = _project_name(db, getattr(asset, "project_id", None))
    if req is not None:
        editor_email = (getattr(req, "last_uploader_email", None) or "").strip() or None
        internal = req.iteration_state["internal_handin"]
        card_url = (internal.get("card_url") or "").strip() or None
        review_url = _review_url(req) or _asset_page_url(asset)
    else:
        editor_email = _responsible_editor_email(db, asset, version_id)
        page = _asset_page_url(asset)
        card_url = page
        review_url = page
    if not editor_email or not card_url:
        return None
    return {
        "editor_email": editor_email,
        "card_url": card_url,
        "review_url": review_url,
        "client": client,
        "title": title,
    }


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
    """A guest-reviewer (client) comment on any asset routes to the responsible editor. Never fires
    for a team comment (`author_id` set, `guest_author_id` None) or an auto-review finding (stored
    `visibility="internal"` at write time by `_guest_comment_visibility` / `publish_review_comment` -
    see routers/comments.py). The hub webhook reads these fields FLAT (comment_id / comment_body)."""
    if not is_enabled():
        return
    if comment.guest_author_id is None or getattr(comment, "visibility", "public") == "internal":
        return
    ctx = _asset_report_context(db, asset, getattr(comment, "version_id", None))
    if ctx is None:
        return
    event = {
        "event": "client_comment",
        "card_url": ctx["card_url"],
        "editor_email": ctx["editor_email"],
        "comment_id": str(comment.id),
        "comment_body": comment.body,
        "author_name": author_name,
        "version_id": str(comment.version_id),
    }
    if ctx["review_url"]:
        event["review_url"] = ctx["review_url"]
    if ctx["client"]:
        event["client"] = ctx["client"]
    if ctx["title"]:
        event["title"] = ctx["title"]
    _post(event)


def announce_revision_submitted(db: Session, asset, version_id) -> None:
    """A new version completed (routers/upload.py `complete`) - the stop signal that answers the open
    client revisions on this asset, whatever path it came through. Keyed on the same per-asset url as
    the comment event so the hub resolves the matching rows."""
    if not is_enabled():
        return
    ctx = _asset_report_context(db, asset, version_id)
    if ctx is None:
        return
    _post({
        "event": "revision_submitted",
        "card_url": ctx["card_url"],
        "editor_email": ctx["editor_email"],
        "version_id": str(version_id),
    })
