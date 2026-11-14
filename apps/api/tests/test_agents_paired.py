"""GET /internal/agents/paired: bridge secret only; paired = a live agent key in a project the human belongs to."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from apps.api.config import settings
from apps.api.main import app
from .agent_pg import env, needs_pg  # noqa: F401

URL = "/internal/agents/paired"


def test_needs_the_bridge_secret(monkeypatch):
    c = TestClient(app)
    monkeypatch.setattr(settings, "review_bridge_secret", "")
    assert c.get(URL, params={"email": "a@x.com"}).status_code == 503
    monkeypatch.setattr(settings, "review_bridge_secret", "s3cret")
    assert c.get(URL, params={"email": "a@x.com"}).status_code == 401
    assert c.get(URL, params={"email": "a@x.com"}, headers={"Authorization": "Bearer nope"}).status_code == 401


@needs_pg
def test_paired_only_with_a_live_key_in_the_humans_project(env, monkeypatch):
    from apps.api.models.agent import AgentKey
    from apps.api.routers.agents_paired import paired_for
    from apps.api.services import agents as agent_service
    with env.Session() as db:
        assert paired_for(db, env.owner.email) == {"paired": False, "last_used_at": None}
        project = db.get(type(env.project_a), env.project_a.id)
        key, row = agent_service.create_key(db, project, env.owner, "Cutter", "claude-code", "deliver")
        row.last_used_at = datetime(2026, 11, 1, tzinfo=timezone.utc)
        db.commit()
        got = paired_for(db, env.owner.email.upper())
        assert got["paired"] is True and got["last_used_at"].startswith("2026-11-01")
        assert paired_for(db, env.user("Stranger").email)["paired"] is False
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
        assert paired_for(db, env.owner.email)["paired"] is False
