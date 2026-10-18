"""Every past public comment, page by page, for the AutoReview Brand Loop backfill.

The live hook (brand_loop.py) only sees comments written after it was switched on, and only on
projects with an explicit brand slug. Turning all earlier client feedback into brand rules needs
the history: this pages through it in the row shape feedback-agent's
scripts/brand-loop-backfill.mjs reads, so that script compresses it per brand into rule drafts
(switched off until someone approves them). Internal comments never leave FreeFrame, same as the
live hook.
"""
import uuid
from datetime import datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models.asset import Asset, AssetVersion
from ..models.comment import Comment
from ..models.project import Project
from ..models.user import GuestUser, User
from . import brand_loop

MAX_LIMIT = 1000


def brand_slug_of(project) -> str | None:
    """The explicit Brand Loop slug, else the confirmed review brand. Never guessed from the name."""
    slug = getattr(project, "autoreview_brand_slug", None)
    if slug:
        return slug
    binding = getattr(project, "review_brand_binding", None)
    return binding.get("brand_slug") if isinstance(binding, dict) and binding.get("brand_slug") else None


def export_row(comment, asset, project, version_number, email, *, staff: bool) -> dict:
    """One comment in the backfill's row shape, plus ids for idempotent imports.
    `bot` = written by the automation reviewer (it carries a review source), never client feedback."""
    email = (email or "").strip().lower()
    return {
        "id": str(comment.id),
        "brand": project.name,
        "brand_slug": brand_slug_of(project),
        "project_id": str(project.id),
        "label": asset.name,
        "asset_id": str(asset.id),
        "version": version_number,
        "text": comment.body,
        "tc": comment.timecode_start,
        "at": comment.created_at.isoformat() if comment.created_at else None,
        "resolved": bool(comment.resolved),
        "parent": str(comment.parent_id) if comment.parent_id else None,
        "bot": comment.review_source is not None,
        "email_dom": email.rsplit("@", 1)[1] if "@" in email else None,
        "client": not staff,
    }


def export_comments(db: Session, *, after: datetime | None = None, after_id: uuid.UUID | None = None,
                    project_id: uuid.UUID | None = None, limit: int = 500) -> dict:
    """Oldest first, keyset paging on (created_at, id) so a long backfill can resume anywhere."""
    limit = max(1, min(limit, MAX_LIMIT))
    q = (db.query(Comment, Asset, Project, AssetVersion.version_number, User.email, GuestUser.email)
         .join(Asset, Asset.id == Comment.asset_id)
         .join(Project, Project.id == Asset.project_id)
         .outerjoin(AssetVersion, AssetVersion.id == Comment.version_id)
         .outerjoin(User, User.id == Comment.author_id)
         .outerjoin(GuestUser, GuestUser.id == Comment.guest_author_id)
         .filter(Comment.deleted_at.is_(None), Comment.visibility == "public"))
    if project_id:
        q = q.filter(Asset.project_id == project_id)
    if after:
        newer = Comment.created_at > after
        if after_id:
            newer = or_(newer, and_(Comment.created_at == after, Comment.id > after_id))
        q = q.filter(newer)
    rows = q.order_by(Comment.created_at, Comment.id).limit(limit).all()

    staff_by_email: dict[str, bool] = {}  # one directory lookup per author, not per comment
    items = []
    for comment, asset, project, version_number, user_email, guest_email in rows:
        email = user_email or guest_email or ""
        if email not in staff_by_email:
            staff_by_email[email] = brand_loop.is_aditor_staff(email)
        items.append(export_row(comment, asset, project, version_number, email, staff=staff_by_email[email]))
    last = rows[-1][0] if len(rows) == limit else None
    return {"items": items,
            "next": {"after": last.created_at.isoformat(), "after_id": str(last.id)} if last else None}
