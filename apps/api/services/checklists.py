"""Durable intent/outbox and version binding. No model/provider logic here."""
import hashlib
import json
import math
import re
import rfc8785
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from ..models.checklist_binding import ChecklistBinding
from ..models.user import User, UserStatus
from ..services import review_bridge


def canonical_json(value) -> str:
    def check(v):
        if v is None or isinstance(v, (str, bool)):
            return
        if isinstance(v, (int, float)) and math.isfinite(v) and abs(v) <= 9007199254740991:
            return
        if isinstance(v, list):
            for x in v: check(x)
            return
        if isinstance(v, dict) and all(isinstance(k, str) and k.isascii() and k and all(32 <= ord(c) <= 126 for c in k) for k in v):
            for x in v.values(): check(x)
            return
        raise ValueError('canonical-value')
    check(value)
    return rfc8785.dumps(value).decode('utf-8')


def snapshot_digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def reserve_binding(db, project_id, user_id, source_key, intent, trello_card_id=None):
    """Constraint is the arbiter; a row lock serializes assignment/folder adoption.

    Tombstones retain their uniqueness, so a deleted assignment cannot silently resurrect.
    """
    digest = snapshot_digest(intent)
    db.execute(insert(ChecklistBinding).values(id=uuid.uuid4(), project_id=project_id, created_by=user_id,
        source_key=source_key, intent=intent, intent_sha256=digest, trello_card_id=trello_card_id,
        status='queued', attempts=0).on_conflict_do_nothing(constraint='uq_checklist_project_source'))
    row = db.query(ChecklistBinding).filter(ChecklistBinding.project_id == project_id,
        ChecklistBinding.source_key == source_key).with_for_update().one()
    if row.deleted_at is not None:
        raise HTTPException(409, 'Assignment was deleted')
    if row.intent_sha256 != digest:
        raise HTTPException(409, 'Assignment already has a different brief; create a new request')
    return row


def validate_snapshot(row, response):
    s = response.get('snapshot')
    if not isinstance(s, dict) or s.get('schema_version') != 'autoreview.plan-request.v1' or s.get('tenant_id') != str(row.project_id) or s.get('request_id') != str(row.id) or s.get('idempotency_key') != f'checklist:{row.project_id}:{row.id}' or snapshot_digest(s) != response.get('context_sha256'):
        raise ValueError('snapshot-identity-invalid')
    return s


def binding_out(row):
    plan = row.plan or {}
    return {'id': str(row.id), 'status': row.status, 'error_code': row.error_code,
        'plan_id': row.plan_id, 'content_sha256': row.content_sha256,
        'registration_error': getattr(row, 'registration_error', None),
        'requirements': plan.get('requirements', []) if row.status == 'ready' else [],
        'limitations': plan.get('limitations', []), 'trello_card_id': getattr(row, 'trello_card_id', None), 'attempts': row.attempts}


def binding_for_folder(db, binding_id, project_id, description):
    row = db.query(ChecklistBinding).filter(ChecklistBinding.id == binding_id,
        ChecklistBinding.deleted_at.is_(None)).with_for_update().first()
    if row is None or row.project_id != project_id:
        raise HTTPException(404, 'Checklist not found')
    if row.request_id is not None or row.trello_card_id is None:
        raise HTTPException(409, 'Checklist belongs to another assignment')
    # The exact canonical card or the originally resolved short URL is required.
    import re
    cards = re.findall(r'https://(?:www\.)?trello\.com/c/([A-Za-z0-9]+)', description or '')
    original = re.search(r'/c/([A-Za-z0-9]+)', row.intent.get('brief_url', ''))
    if not cards or any(c not in {row.trello_card_id, row.intent.get('trello_short_link', ''), original.group(1) if original else ''} for c in cards):
        raise HTTPException(409, 'Folder card differs from checklist')
    return row


def _failed_attempt(row, code):
    row.error_code = code
    row.status = 'failed' if row.attempts >= 3 or code in {'plan-api-unavailable', 'review-unconfigured', 'plan-conflict', 'snapshot-conflict', 'snapshot-identity-invalid', 'plan-contract-invalid', 'source-not-authorized'} else 'queued'
    row.next_attempt_at = None if row.status == 'failed' else datetime.now(timezone.utc) + timedelta(seconds=30 * row.attempts)


def pending_registration(row):
    row.registered_at = None
    row.registration_attempts = 0
    row.registration_error = None
    row.next_registration_at = None


def _verify_request_card(db, row):
    """Resolve missing staff-request metadata without changing the original intent."""
    try:
        is_trello = urlparse(row.intent.get('brief_url', '')).hostname in {'trello.com', 'www.trello.com'}
    except ValueError:
        return None  # Other malformed URLs retain the existing snapshot failure path.
    if not is_trello:
        return None
    if not row.request_id:
        return None if getattr(row, 'trello_card_id', None) else 'source-not-authorized'
    creator = db.query(User).filter(User.id == row.created_by, User.deleted_at.is_(None)).first()
    if creator is None or creator.is_staff is not True or creator.status != UserStatus.active:
        return 'source-not-authorized'
    if getattr(row, 'trello_card_id', None):
        return None
    card = review_bridge.checklist_card(row.intent['brief_url'])
    if not card or not re.fullmatch(r'[a-f0-9]{24}', str(card.get('card_id', ''))) or not re.fullmatch(r'[A-Za-z0-9]{8}', str(card.get('short_link', ''))):
        return 'card-unavailable'
    row.trello_card_id = card['card_id']
    return None


def advance_binding(db, row):
    """Caller holds the binding row lock. Snapshot commit precedes all paid preparation.

    After snapshot commit, next delivery may submit concurrently: identical canonical payload and
    engine idempotency make this safe. No input is reread after the freeze succeeds.
    """
    if row.status in ('ready', 'failed') or (row.next_attempt_at and row.next_attempt_at > datetime.now(timezone.utc)):
        return
    row.attempts += 1
    if row.snapshot is None:
        error = _verify_request_card(db, row)
        if error:
            _failed_attempt(row, error); db.commit(); return
        response = review_bridge.checklist_snapshot({**row.intent, 'tenant_id': str(row.project_id), 'binding_id': str(row.id), **({'trello_card_id': row.trello_card_id} if getattr(row, 'trello_card_id', None) else {})})
        if not response:
            _failed_attempt(row, 'briefing-unavailable'); db.commit(); return
        try:
            row.snapshot = validate_snapshot(row, response)
        except ValueError:
            _failed_attempt(row, 'snapshot-identity-invalid'); db.commit(); return
        row.context_sha256 = response['context_sha256']
        row.status = 'preparing'
        pending_registration(row)
        db.commit()  # This is the freeze; a retry must never reload live rules/briefing.
        db.refresh(row, with_for_update=True)
        if row.status in ('ready', 'failed'):
            return
    response = review_bridge.checklist_plan(row.snapshot, row.context_sha256, row.plan_id)
    if not response or response.get('error'):
        _failed_attempt(row, (response or {}).get('error', 'plan-unavailable')); db.commit(); return
    if response.get('context_sha256') != row.context_sha256 or response.get('status') not in ('queued', 'running', 'ready', 'failed') or not isinstance(response.get('plan_id'), str) or (row.plan_id and row.plan_id != response['plan_id']):
        _failed_attempt(row, 'plan-contract-invalid'); db.commit(); return
    if response['status'] == 'ready' and (not response.get('requirements') or not response.get('content_sha256')):
        _failed_attempt(row, 'plan-contract-invalid'); db.commit(); return
    if (row.plan_id, row.content_sha256) != (response['plan_id'], response.get('content_sha256')):
        pending_registration(row)
    row.plan_id = response['plan_id']
    row.status = 'ready' if response['status'] == 'ready' else 'failed' if response['status'] == 'failed' else 'running'
    row.error_code = 'plan-failed' if row.status == 'failed' else None
    row.plan = response
    row.content_sha256 = response.get('content_sha256')
    row.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=15) if row.status == 'running' else None
    # Successful polling is not a failed attempt; waiting plans can outlive three polls.
    row.attempts = 0
    db.commit()


def dispatch_binding(binding_id):
    from ..tasks.checklist_tasks import prepare_checklist
    from ..tasks.celery_app import send_task_safe
    send_task_safe(prepare_checklist, str(binding_id))
