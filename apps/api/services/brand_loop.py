"""AutoReview Brand Loop: committed comments go to review.aditor.ai, which turns client feedback
into brand rules.

Contract: feedback-agent docs/superpowers/specs/2026-10-16-brand-loop-CONTRACT.md. Off unless both
AUTOREVIEW_URL and BRAND_LOOP_SECRET are set. Fire-and-forget like hub_events.py: the POST runs as
a background task after the response, and nothing here may fail or slow the comment. A comment
missed while AutoReview is down is picked up by its idempotent backfill (keyed on commentId).
"""
import logging

import httpx

from ..config import settings
from ..models.project import Project

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return bool(settings.autoreview_url.strip() and settings.brand_loop_secret.strip())


def queue_comment(background_tasks, db, comment, asset, *, author_email, author_is_client, share_token=None) -> None:
    """Call after the comment is committed. Skips projects without an explicit brand slug and
    non-public comments: internal staff notes (and the automation reviewer's findings, which are
    stored internal) never leave FreeFrame."""
    if background_tasks is None or not is_enabled() or getattr(comment, "visibility", "public") != "public":
        return
    try:
        project = db.query(Project).filter(Project.id == asset.project_id).first()
        slug = getattr(project, "autoreview_brand_slug", None)
        if not slug:
            return
        payload = {
            "v": 1, "commentId": str(comment.id), "brandSlug": slug, "assetId": str(asset.id),
            "shareToken": share_token, "timecode": comment.timecode_start, "body": comment.body,
            "authorEmail": author_email, "authorIsClient": author_is_client,
            "createdAt": comment.created_at.isoformat(),
        }
    except Exception:  # noqa: BLE001 - the comment is saved; the hook must never fail it
        logger.warning("brand loop: could not build payload for comment %s", getattr(comment, "id", None), exc_info=True)
        return
    background_tasks.add_task(post_comment, payload)


def post_comment(payload: dict) -> None:
    try:
        r = httpx.post(
            settings.autoreview_url.strip().rstrip("/") + "/api/brand-loop/comment",
            json=payload,
            headers={"authorization": f"Bearer {settings.brand_loop_secret.strip()}"},
            timeout=3,
        )
        if r.status_code >= 400:
            logger.warning("brand loop: comment %s -> %s", payload.get("commentId"), r.status_code)
    except Exception:  # noqa: BLE001 - fire-and-forget by contract
        logger.warning("brand loop: comment %s not delivered", payload.get("commentId"), exc_info=True)
