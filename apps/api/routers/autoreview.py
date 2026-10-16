"""One-click AutoReview access (Brand Loop B3).

The sidebar asks /autoreview/brands which brand pages the user may open, and /autoreview/link
mints a 60 s HS256 token for one of them. Contract: feedback-agent
docs/superpowers/specs/2026-10-16-brand-loop-CONTRACT.md. The Worker verifies the token, sets its
own session and drops the token from the URL; the secret never reaches a browser.
"""
import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from jose import jwt
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..middleware.auth import get_current_user
from ..models.project import Project, ProjectMember
from ..models.user import User
from ..services import brand_loop

router = APIRouter(prefix="/autoreview", tags=["autoreview"])

TOKEN_SECONDS = 60


def user_brands(db: Session, user: User) -> list[dict]:
    """Brand slugs of live projects the user is a current member of (a live ProjectMember row).
    Creating a project, being superadmin or the instance-wide staff role grant nothing here: the
    Worker admits ADMIN_EMAILS on its own. Label = the oldest such project's name."""
    rows = db.query(Project.autoreview_brand_slug, Project.name).join(ProjectMember, and_(
        ProjectMember.project_id == Project.id, ProjectMember.user_id == user.id,
        ProjectMember.deleted_at.is_(None),
    )).filter(
        Project.autoreview_brand_slug.isnot(None), Project.deleted_at.is_(None),
    ).order_by(Project.autoreview_brand_slug, Project.created_at, Project.id).all()
    brands: dict[str, str] = {}
    for slug, name in rows:
        brands.setdefault(slug, name)
    return [{"slug": slug, "name": name} for slug, name in brands.items()]


@router.get("/brands")
def list_brands(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not brand_loop.is_enabled():
        return {"brands": []}
    return {"brands": user_brands(db, current_user)}


@router.get("/link")
def brand_link(
    brand: str = Query(..., max_length=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not brand_loop.is_enabled():
        raise HTTPException(status_code=503, detail="AutoReview is not configured")
    slugs = [b["slug"] for b in user_brands(db, current_user)]
    if brand not in slugs:
        raise HTTPException(status_code=403, detail="Not a member of this brand")
    token = jwt.encode({
        "v": 1, "iss": "freeframe", "aud": "review:brand", "sub": current_user.email,
        # Only the requested brand: a leaked link opens one brand page, not all of the user's.
        "brands": [brand], "exp": int(time.time()) + TOKEN_SECONDS,
    }, settings.brand_loop_secret.strip(), algorithm="HS256")
    base = settings.autoreview_url.strip().rstrip("/")
    return {"url": f"{base}/brand/{quote(brand, safe='')}?t={token}"}
