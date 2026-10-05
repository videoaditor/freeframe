import uuid
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..middleware.auth import get_current_user, get_identity_user
from ..models.user import User
from ..models.product_feedback import ProductFeedback

router = APIRouter(prefix='/product-feedback', tags=['Product feedback'])


class FeedbackSubmission(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    submission_id: uuid.UUID
    kind: Literal['bug', 'idea']
    message: str = Field(min_length=1, max_length=4000)
    page_path: str | None = Field(default=None, max_length=2000)

    @field_validator('page_path')
    @classmethod
    def safe_page(cls, value):
        if not value or not value.startswith('/') or value.startswith('//'):
            return None
        # Route groups only. IDs, share tokens, query strings and fragments are never stored.
        path = urlsplit(value).path.split('/')[1]
        return '/' + path if path in {'projects', 'requests', 'assets', 'settings', 'feedback', 'campaign'} else None


@router.post('', status_code=201)
def submit_feedback(payload: FeedbackSubmission, user: User = Depends(get_identity_user), db: Session = Depends(get_db)):
    def existing():
        return db.query(ProductFeedback).filter(and_(
            ProductFeedback.author_id == user.id,
            ProductFeedback.submission_id == payload.submission_id,
            ProductFeedback.deleted_at.is_(None),
        )).first()

    row = existing()
    if not row:
        campaign = getattr(user, 'suite_campaign', None)
        campaign_id = campaign.get('id') if isinstance(campaign, dict) else None
        account_id = getattr(user, 'suite_account_id', None)
        row = ProductFeedback(
            id=uuid.uuid4(), author_id=user.id, submission_id=payload.submission_id,
            suite_account_id=account_id if isinstance(account_id, str) else None,
            campaign_id=campaign_id if isinstance(campaign_id, str) else None,
            tool='autoreview', kind=payload.kind, message=payload.message,
            page_path=payload.page_path, triage_status='received',
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = existing()
            if not row:
                raise
    return {'id': str(row.id), 'status': 'received'}


@router.get('')
def list_feedback(
    offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if user.is_staff is not True and user.is_superadmin is not True:
        raise HTTPException(status_code=403, detail='Staff access required')
    rows = db.query(ProductFeedback).filter(ProductFeedback.deleted_at.is_(None)).order_by(
        ProductFeedback.created_at.desc(), ProductFeedback.id.desc(),
    ).offset(offset).limit(limit + 1).all()
    return {
        'items': [{key: getattr(row, key) for key in (
            'id', 'author_id', 'suite_account_id', 'campaign_id', 'tool', 'kind',
            'message', 'page_path', 'triage_status', 'created_at', 'digest_id',
        )} for row in rows[:limit]],
        'next_offset': offset + limit if len(rows) > limit else None,
    }
