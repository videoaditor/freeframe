"""Operator-only intent; normal owners/guests and read-only API keys cannot write."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.review_timing import attest_request_timing, set_timing_purpose, admit_timing, timing_status
from .checklists import require_review_bridge

router = APIRouter(tags=['internal-review-timing'], dependencies=[Depends(require_review_bridge)])


@router.get('/internal/review/timing-intent/{request_id}', include_in_schema=False)
def dry_run(request_id: uuid.UUID, project_id: uuid.UUID, response: Response,
    share_token: str = Query(min_length=1, max_length=64), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return attest_request_timing(db, request_id, project_id, share_token)


class NaturalIntent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: uuid.UUID
    share_token: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    customer_order_verified: Literal[True]


@router.post('/internal/review/timing-intent/{request_id}', include_in_schema=False)
def apply_intent(request_id: uuid.UUID, body: NaturalIntent, response: Response, db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    result = attest_request_timing(db, request_id, body.project_id, body.share_token, apply=True)
    db.commit()
    return result


class TimingPurpose(BaseModel):
    model_config = ConfigDict(extra='forbid')
    purpose: Literal['operator-test', 'synthetic'] | None


class TimingPurposePatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quiet: StrictBool | None = None
    provenance: Literal['operator-test', 'synthetic'] | None = None

    @model_validator(mode='after')
    def explicit_flags(self):
        if not self.model_fields_set or ('quiet' in self.model_fields_set and self.quiet is None):
            raise ValueError('Explicit quiet/provenance patch required')
        return self


@router.post('/internal/review/timing-purpose/{share_token}', include_in_schema=False)
def apply_purpose(share_token: str, body: TimingPurpose | TimingPurposePatch, response: Response, db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    result = (set_timing_purpose(db, share_token, body.purpose) if isinstance(body, TimingPurpose)
        else set_timing_purpose(db, share_token, patch=body.model_dump(exclude_unset=True)))
    db.commit()
    return result


class TimingAdmission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: uuid.UUID
    share_token: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    asset_id: uuid.UUID
    version_id: uuid.UUID
    exclusion: Literal['operator-test', 'synthetic', 'unknown', 'unclassified'] | None = None


@router.post('/internal/review/timing-admission/{request_id}', include_in_schema=False)
def apply_admission(request_id: uuid.UUID, body: TimingAdmission, response: Response, db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    result = admit_timing(db, request_id, body.project_id, body.share_token, body.asset_id, body.version_id, body.exclusion)
    db.commit()
    return result


class TimingIdentity(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: uuid.UUID
    asset_id: uuid.UUID
    version_id: uuid.UUID
    provenance_attestation: str = Field(pattern=r'^[a-f0-9]{64}$')


class TimingStatus(BaseModel):
    model_config = ConfigDict(extra='forbid')
    versions: list[TimingIdentity] = Field(max_length=1000)


@router.post('/internal/review/timing-status', include_in_schema=False)
def read_status(body: TimingStatus, response: Response, db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return timing_status(db, body.versions)
