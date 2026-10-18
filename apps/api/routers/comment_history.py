"""Server-to-server comment history for the AutoReview Brand Loop backfill (review bridge secret)."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.comment_history import MAX_LIMIT, export_comments
from .checklists import require_review_bridge

router = APIRouter(tags=['internal-comment-history'], dependencies=[Depends(require_review_bridge)])


@router.get('/internal/review/comments-export', include_in_schema=False)
def comments_export(response: Response, after: datetime | None = None, after_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None, limit: int = Query(500, ge=1, le=MAX_LIMIT), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return export_comments(db, after=after, after_id=after_id, project_id=project_id, limit=limit)
