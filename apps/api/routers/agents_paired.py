"""Server-to-server: does this person have a live agent key in one of their projects? (review bridge secret)

AutoReview's worker proxies this for Gen's Agent tab, so a Claude that has been connected for weeks counts
without ever calling whoami. Answers a boolean and the latest use, never keys, names or projects.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.agent import AgentKey
from ..models.project import ProjectMember
from ..models.user import User
from .checklists import require_review_bridge

router = APIRouter(tags=['internal-agents-paired'], dependencies=[Depends(require_review_bridge)])


def paired_for(db: Session, email: str) -> dict:
    """paired: a non-revoked key in a project this (human) email is a member of. last_used_at: its latest use."""
    human = db.query(User.id).filter(func.lower(User.email) == email.strip().lower(), User.kind != 'agent')
    row = (db.query(func.count(AgentKey.id), func.max(AgentKey.last_used_at))
           .join(ProjectMember, ProjectMember.project_id == AgentKey.project_id)
           .filter(ProjectMember.user_id.in_(human), ProjectMember.deleted_at.is_(None), AgentKey.revoked_at.is_(None))
           .one())
    last: datetime | None = row[1]
    return {'paired': bool(row[0]), 'last_used_at': last.isoformat() if last else None}


@router.get('/internal/agents/paired', include_in_schema=False)
def agents_paired(response: Response, email: str = Query(min_length=3, max_length=255), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return paired_for(db, email)
