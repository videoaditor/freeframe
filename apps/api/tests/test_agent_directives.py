"""Card directives on an agent request: the list is stored, a repeat REPLACES it ([] removes it), the review hears
every change, and a request without directives behaves as before."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from .agent_pg import env, needs_pg  # noqa: F401

SAID = "the presenter is visibly in frame"
LINE = {"id": "d1", "text": SAID, "by": "Alan", "at": "2026-11-23T10:00:00Z"}


def test_apply_directives_stores_replaces_and_clears_and_tells_the_review():
    from apps.api.routers import agent
    req, db = SimpleNamespace(directives=None, review_share_token="share-1"), MagicMock()
    with patch.object(agent.review_bridge, "set_directives") as push:
        agent._apply_directives(db, req, agent.NewRequest(title="t", external_ref="e", directives=[agent.Directive(**LINE)]))
        assert req.directives == [LINE] and push.call_args.args == ("share-1", [LINE])
        agent._apply_directives(db, req, agent.NewRequest(title="t", external_ref="e", directives=[]))
        assert req.directives is None and push.call_args.args == ("share-1", [])
        push.reset_mock()
        agent._apply_directives(db, req, agent.NewRequest(title="t", external_ref="e"))  # omitted: nothing happens
        assert push.call_count == 0


def test_directive_limits():
    from apps.api.routers import agent
    with pytest.raises(ValidationError):
        agent.Directive(id="x", text="a" * 501)
    with pytest.raises(ValidationError):
        agent.NewRequest(title="t", external_ref="e", directives=[agent.Directive(**LINE)] * 21)


@needs_pg
def test_create_and_repeat_over_http(env):
    from apps.api.models.upload_request import UploadRequest
    from apps.api.routers import agent
    agent_key = env.pair_agent(env.project_a)
    body = {"title": "Chess", "external_ref": "card-d", "directives": [LINE]}
    with patch.object(agent.review_bridge, "set_directives") as push:
        first = env.client.post("/agent/requests", json=body, headers=agent_key.headers).json()
        assert first["created"] is True and first["directives"] == [LINE]
        plain = env.client.post("/agent/requests", json={"title": "Chess", "external_ref": "card-d"}, headers=agent_key.headers).json()
        assert plain["directives"] == [LINE] and push.call_count == 1  # omitted: untouched
        cleared = env.client.post("/agent/requests", json={**body, "directives": []}, headers=agent_key.headers).json()
        assert cleared["request_id"] == first["request_id"] and cleared["directives"] == []
        assert push.call_args.args[1] == []
    with env.Session() as db:
        assert db.get(UploadRequest, uuid.UUID(first["request_id"])).directives is None
