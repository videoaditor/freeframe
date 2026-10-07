"""Parts and complete ads share durable registration without mixing their reviewers."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

from apps.api.config import settings
from apps.api.tasks.checklist_tasks import _register


def test_parts_registration_retains_frozen_brief_and_excludes_ordinary_folder_review(monkeypatch):
    sent = []

    def request(method, url, **kwargs):
        sent.append(kwargs['json'])
        return httpx.Response(200, json={'ok': True}, request=httpx.Request(method, url))

    monkeypatch.setattr(settings, 'review_bridge_url', 'https://review.example.test')
    monkeypatch.setattr(settings, 'review_bridge_secret', 'synthetic-test-secret')
    monkeypatch.setattr(httpx, 'request', request)
    row = SimpleNamespace(
        id=uuid.uuid4(), project_id=uuid.uuid4(), registered_at=None,
        review_share_token='synthetic-parts-share', registration_attempts=0,
        next_registration_at=None, context_sha256='a' * 64, plan_id=None,
        content_sha256=None, snapshot={'briefing': {'text': 'Frozen original brief'}},
        intent={'brand': 'demo', 'title': 'Parts', 'brief_text': 'Mutable input',
                'receive_iterations': True},
    )
    _register(MagicMock(), row)
    assert sent[0]['receive_iterations'] is True
    assert sent[0]['brief_text'] == 'Frozen original brief'
    assert sent[0]['checklist']['binding_id'] == str(row.id)
    assert row.registered_at is not None
