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
from sqlalchemy import and_, func, or_
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
    """Brand slugs of live projects the user created or is an explicit member of; superadmins get
    every linked brand. The instance-wide staff role deliberately does not count: it would hand
    every account every brand page."""
    query = db.query(Project.autoreview_brand_slug, func.min(Project.name)).filter(
        Project.autoreview_brand_slug.isnot(None), Project.deleted_at.is_(None))
    if not user.is_superadmin:
        query = query.outerjoin(ProjectMember, and_(
            ProjectMember.project_id == Project.id, ProjectMember.user_id == user.id,
            ProjectMember.deleted_at.is_(None),
        )).filter(or_(ProjectMember.id.isnot(None), Project.created_by == user.id))
    rows = query.group_by(Project.autoreview_brand_slug).order_by(Project.autoreview_brand_slug).all()
    return [{"slug": slug, "name": name} for slug, name in rows]


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
        "brands": slugs, "exp": int(time.time()) + TOKEN_SECONDS,
    }, settings.brand_loop_secret.strip(), algorithm="HS256")
    base = settings.autoreview_url.strip().rstrip("/")
    return {"url": f"{base}/brand/{quote(brand, safe='')}?t={token}"}
