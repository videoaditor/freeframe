import hashlib
import uuid
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..services import feedback_recordings, s3_service
from ..middleware.auth import get_current_user, get_identity_user
from ..middleware.rate_limit import rate_limit
from ..models.user import User
from ..models.product_feedback import ProductFeedback, FeedbackRecording

router = APIRouter(prefix='/product-feedback', tags=['Product feedback'])


class FeedbackSubmission(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    submission_id: uuid.UUID
    kind: Literal['bug', 'idea']
    message: str = Field(default='', max_length=4000)
    recording_id: uuid.UUID | None = None
    page_path: str | None = Field(default=None, max_length=2000)

    @model_validator(mode='after')
    def require_content(self):
        if not self.message and not self.recording_id:
            raise ValueError('A message or saved recording is required')
        return self

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
        if payload.recording_id:
            get_recording(payload.recording_id, user, db)
        campaign = getattr(user, 'suite_campaign', None)
        campaign_id = campaign.get('id') if isinstance(campaign, dict) else None
        account_id = getattr(user, 'suite_account_id', None)
        row = ProductFeedback(
            id=uuid.uuid4(), author_id=user.id, submission_id=payload.submission_id,
            suite_account_id=account_id if isinstance(account_id, str) else None,
            campaign_id=campaign_id if isinstance(campaign_id, str) else None,
            tool='autoreview', kind=payload.kind, message=payload.message,
            page_path=payload.page_path, triage_status='received', recording_id=payload.recording_id,
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
            'message', 'page_path', 'triage_status', 'created_at', 'digest_id', 'recording_id',
        )} for row in rows[:limit]],
        'next_offset': offset + limit if len(rows) > limit else None,
    }


def get_recording(recording_id: uuid.UUID, user: User, db: Session, *, allow_staff=False, lock=False):
    query = db.query(FeedbackRecording).filter(and_(
        FeedbackRecording.id == recording_id, FeedbackRecording.deleted_at.is_(None),
    ))
    if lock:
        # Owner-scoped row lock serializes concurrent retries before a paid call.
        query = query.filter(FeedbackRecording.author_id == user.id).with_for_update()
    row = query.first()
    staff = allow_staff and (user.is_staff is True or user.is_superadmin is True)
    if not row or (row.author_id != user.id and not staff):
        raise HTTPException(404, 'Recording not found')
    return row


@router.post('/recordings', status_code=201, dependencies=[Depends(rate_limit('feedback_audio_upload', 10, 600))])
def save_recording(
    recording_id: uuid.UUID = Form(...), file: UploadFile = File(...),
    user: User = Depends(get_identity_user), db: Session = Depends(get_db),
):
    data = file.file.read(settings.product_feedback_audio_max_bytes + 1)
    if len(data) > settings.product_feedback_audio_max_bytes:
        raise HTTPException(413, 'Recording exceeds the upload limit')
    kind = feedback_recordings.validate_container(data, file.content_type or '')
    digest = hashlib.sha256(data).hexdigest()

    def existing():
        row = db.query(FeedbackRecording).filter(and_(
            FeedbackRecording.id == recording_id, FeedbackRecording.deleted_at.is_(None),
        )).first()
        if row and row.author_id != user.id:
            raise HTTPException(404, 'Recording not found')
        if row and row.content_sha256 != digest:
            raise HTTPException(409, 'Recording ID already contains different audio')
        return row

    row = existing()
    if not row:
        feedback_recordings.normalize_audio(data)
        key = f'product-feedback/audio/{user.id}/{recording_id}/{digest}.{kind}'
        content_type = 'audio/' + kind
        s3_service.put_object(key, data, content_type=content_type, cache_control='private, no-store')
        row = FeedbackRecording(id=recording_id, author_id=user.id, s3_key=key,
                                content_sha256=digest, content_type=content_type)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = existing()
            if not row:
                raise
    return {'id': str(row.id), 'status': 'saved'}


@router.get('/recordings/{recording_id}')
def recording_playback(recording_id: uuid.UUID, user: User = Depends(get_identity_user), db: Session = Depends(get_db)):
    row = get_recording(recording_id, user, db, allow_staff=True)
    return {'id': str(row.id), 'url': s3_service.generate_presigned_get_url(row.s3_key, expires_in=300),
            'transcript': row.transcript}


@router.post('/recordings/{recording_id}/transcribe', dependencies=[Depends(rate_limit('feedback_audio_transcribe', 10, 600))])
def transcribe_recording(recording_id: uuid.UUID, user: User = Depends(get_identity_user), db: Session = Depends(get_db)):
    row = get_recording(recording_id, user, db, lock=True)
    if row.transcript is not None:
        return {'status': 'transcribed', 'text': row.transcript}
    if not settings.product_feedback_whisper_model:
        return {'status': 'unavailable', 'text': None}
    try:
        body = s3_service.get_s3_client().get_object(Bucket=settings.s3_bucket, Key=row.s3_key)['Body']
        try:
            data = body.read(settings.product_feedback_audio_max_bytes + 1)
        finally:
            body.close()
        if len(data) > settings.product_feedback_audio_max_bytes:
            return {'status': 'failed', 'text': None}
        text = feedback_recordings.transcribe_audio(data)
    except Exception:
        # No provider error payloads or user audio in logs/responses. The already
        # committed original is never removed when conversion/transcription fails.
        return {'status': 'failed', 'text': None}
    row.transcript = text
    db.commit()
    return {'status': 'transcribed', 'text': text}
