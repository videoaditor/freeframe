"""A standing share link for an automation, created with the project and announced once.

Aditor's Auto Review has no FreeFrame account. That is deliberate - it comments as a guest using
only a share token, which is why it needs no login, no password and no admin invite. The cost is
that it can only see a project somebody has explicitly shared with it, so every project needed a
link created by hand and pasted somewhere. One folder got one; the rest were invisible - not
broken, just unwatched, which is the harder failure to notice.

So: when a project is created, create ONE standing link for the automation and POST it to a
configured URL. The automation learns about the project the moment it exists, and nobody clicks
anything.

Both halves are off by default. No webhook URL configured means none of this runs, and an
instance that does not use an automation behaves exactly as it does now.

Failure here must never fail the project. A share link the automation never hears about is a
project it does not watch; a project that could not be created is an editor who cannot work.
"""

import logging
import secrets
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models.share import ShareLink, SharePermission

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return bool((getattr(settings, "automation_share_webhook_url", "") or "").strip())


def create_standing_link(db: Session, project_id, created_by) -> Optional[ShareLink]:
    """A project-scoped link with the two switches the automation actually needs.

    `comment` and `allow_download` are not decoration: without commenting it cannot post the
    review, and without downloads only the streaming copy exists, which cannot be analysed. Those
    are the two conditions that have silently blocked real reviews, so they are set here rather
    than left to whoever creates the project.

    No expiry. A standing link that quietly dies takes the project's reviews with it, and that has
    already happened once with a link that had been shared by hand.
    """
    if not is_enabled():
        return None
    link = ShareLink(
        project_id=project_id,
        token=secrets.token_urlsafe(32),
        created_by=created_by,
        title="Auto Review",
        description="Standing link so Auto Review can see this project. Safe to leave in place.",
        permission=SharePermission.comment,
        allow_download=True,
        visibility="public",
    )
    db.add(link)
    db.flush()
    return link


def announce(project, link: ShareLink) -> None:
    """Tell the automation the project exists. Best effort, never raises."""
    url = (getattr(settings, "automation_share_webhook_url", "") or "").strip()
    if not url or link is None:
        return
    secret = (getattr(settings, "automation_share_webhook_secret", "") or "").strip()
    base = (getattr(settings, "frontend_url", "") or "").rstrip("/")
    try:
        httpx.post(
            url,
            json={
                "project_id": str(project.id),
                "project_name": project.name,
                # The description carries the brief link, which is how the automation works out
                # which brand and which card this project belongs to.
                "description": project.description or "",
                "share_token": link.token,
                "share_url": f"{base}/share/{link.token}" if base else None,
            },
            headers={"authorization": f"Bearer {secret}"} if secret else {},
            timeout=10,
        )
    except Exception:  # noqa: BLE001 - a webhook must never fail a project creation
        logger.warning("automation share webhook failed for project %s", project.id, exc_info=True)
