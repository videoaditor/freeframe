"""Staff file requests must verify Trello identity before freezing their context."""
import hashlib
import json
import uuid
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.api.models.user import UserStatus
from apps.api.services import checklists

CARD = {'card_id': '0123456789abcdef01234567', 'short_link': 'AbCd1234'}


@pytest.fixture
def request_context(monkeypatch):
    creator = SimpleNamespace(id=uuid.uuid4(), is_staff=True, status=UserStatus.active, deleted_at=None)
    intent = {'brand': 'synthetic', 'title': 'Synthetic request', 'brief_text': 'Full original brief',
        'brief_url': 'https://trello.com/c/AbCd1234/example', 'brief_pdf_base64': ''}
    row = SimpleNamespace(id=uuid.uuid4(), project_id=uuid.uuid4(), created_by=creator.id,
        request_id=uuid.uuid4(), trello_card_id=None, intent=intent, intent_sha256='original-intent-hash',
        snapshot=None, context_sha256=None, status='queued', attempts=0, error_code=None,
        next_attempt_at=None, plan_id=None, content_sha256=None, plan=None)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = creator
    calls = {'card': 0, 'snapshot': 0}

    def card(url):
        calls['card'] += 1
        assert url == intent['brief_url']
        return CARD.copy()

    def snapshot(payload):
        calls['snapshot'] += 1
        if payload.get('trello_card_id') != CARD['card_id']:
            return None  # The real Worker rejects this before private Trello access.
        saved = {'schema_version': 'autoreview.plan-request.v1', 'tenant_id': str(row.project_id),
            'request_id': str(row.id), 'idempotency_key': f'checklist:{row.project_id}:{row.id}',
            'briefing': {'text': 'Verified full card brief', 'version': 'v1', 'sources': []},
            'rules': [{'id': 'frozen-rule', 'what': 'Show product', 'sources': []}],
            'brand_context': {'brand': 'synthetic', 'text': 'Frozen brand note', 'sources': []}, 'limitations': []}
        digest = hashlib.sha256(json.dumps(saved, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return {'snapshot': saved, 'context_sha256': digest}

    monkeypatch.setattr(checklists.review_bridge, 'checklist_card', card)
    monkeypatch.setattr(checklists.review_bridge, 'checklist_snapshot', snapshot)
    monkeypatch.setattr(checklists.review_bridge, 'checklist_plan', lambda *_: {'error': 'plan-api-unavailable'})
    return SimpleNamespace(row=row, creator=creator, db=db, calls=calls, snapshot=snapshot)


def test_staff_request_freezes_context_after_canonical_card_verification(request_context):
    c = request_context
    original = deepcopy(c.row.intent)
    checklists.advance_binding(c.db, c.row)
    assert c.row.snapshot is not None
    assert c.row.snapshot['briefing']['text'] == 'Verified full card brief'
    assert c.row.snapshot['rules'][0]['id'] == 'frozen-rule'
    assert c.row.trello_card_id == CARD['card_id']
    assert c.row.intent == original
    assert c.row.intent_sha256 == 'original-intent-hash'
    assert c.row.error_code == 'plan-api-unavailable'
    assert c.calls == {'card': 1, 'snapshot': 1}


@pytest.mark.parametrize('untrusted', ['customer', 'deactivated', 'missing', 'not-request'])
def test_unverified_request_cannot_use_private_trello_service(request_context, monkeypatch, untrusted):
    c = request_context
    if untrusted == 'customer':
        c.creator.is_staff = False
    elif untrusted == 'deactivated':
        c.creator.status = UserStatus.deactivated
    elif untrusted == 'missing':
        c.db.query.return_value.filter.return_value.first.return_value = None
    else:
        c.row.request_id = None

    def forbidden(*_):
        pytest.fail('Untrusted request reached the private source service')

    monkeypatch.setattr(checklists.review_bridge, 'checklist_card', forbidden)
    monkeypatch.setattr(checklists.review_bridge, 'checklist_snapshot', forbidden)
    checklists.advance_binding(c.db, c.row)
    assert c.row.snapshot is None
    assert c.row.trello_card_id is None
    assert c.row.status == 'failed'
    assert c.row.error_code == 'source-not-authorized'


@pytest.mark.parametrize('card', [None, {'card_id': 'not-canonical', 'short_link': 'AbCd1234'},
    {'card_id': CARD['card_id'], 'short_link': ''}])
def test_card_verification_failure_never_reads_private_brief(request_context, monkeypatch, card):
    c = request_context
    monkeypatch.setattr(checklists.review_bridge, 'checklist_card', lambda *_: card)
    checklists.advance_binding(c.db, c.row)
    assert c.row.snapshot is None
    assert c.row.trello_card_id is None
    assert c.row.status == 'queued'
    assert c.row.error_code == 'card-unavailable'
    assert c.calls['snapshot'] == 0


def test_verified_card_survives_snapshot_outage_without_changing_intent(request_context, monkeypatch):
    c = request_context
    original = deepcopy(c.row.intent)
    monkeypatch.setattr(checklists.review_bridge, 'checklist_snapshot', lambda *_: None)
    checklists.advance_binding(c.db, c.row)
    assert c.row.trello_card_id == CARD['card_id']
    assert c.row.error_code == 'briefing-unavailable'
    c.row.next_attempt_at = None
    monkeypatch.setattr(checklists.review_bridge, 'checklist_snapshot', c.snapshot)
    checklists.advance_binding(c.db, c.row)
    assert c.row.snapshot is not None
    assert c.calls['card'] == 1
    assert c.row.intent == original


def test_frozen_request_retry_never_reloads_card_or_snapshot(request_context, monkeypatch):
    c = request_context
    checklists.advance_binding(c.db, c.row)
    assert c.row.snapshot is not None
    frozen = deepcopy(c.row.snapshot)
    digest = c.row.context_sha256
    c.row.status = 'queued'  # The existing authenticated retry resets terminal plan status.

    def forbidden(*_):
        pytest.fail('Frozen snapshot retry reloaded mutable source data')

    monkeypatch.setattr(checklists.review_bridge, 'checklist_card', forbidden)
    monkeypatch.setattr(checklists.review_bridge, 'checklist_snapshot', forbidden)
    c.db.query.side_effect = forbidden
    checklists.advance_binding(c.db, c.row)
    assert c.row.snapshot == frozen
    assert c.row.context_sha256 == digest
