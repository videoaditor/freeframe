import uuid
from unittest.mock import MagicMock

from apps.api.config import settings
from apps.api.services import review_bridge


def test_bridge_additions_are_keyword_only_and_default_legacy(monkeypatch):
    calls = []
    monkeypatch.setattr(review_bridge, "_call", lambda *a, **kw: calls.append(kw) or {"ok": True})
    review_bridge.register_request("share", "brand", "title", tenant_id="freeframe:project:p", request_id="r")
    assert calls[0]["json"]["engine"] == "legacy"
    assert calls[0]["json"]["tenant_id"] == "freeframe:project:p"
    assert calls[0]["json"]["request_id"] == "r"


def test_bridge_invalid_selection_is_unavailable_without_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(review_bridge, "_call", lambda *a, **kw: calls.append(kw))
    assert review_bridge.register_request("s", "b", "t", engine="other") is None
    assert calls == []


def test_create_request_uses_committed_authorized_project_identity(monkeypatch):
    from apps.api.routers import requests as rq
    from apps.api.models.project import Project
    from apps.api.models.upload_request import UploadRequest
    project = Project(id=uuid.uuid4(), name="Synthetic project", created_by=uuid.uuid4())
    user = MagicMock(id=uuid.uuid4())
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = project
    monkeypatch.setattr(rq, "require_project_role", lambda *a: None)
    monkeypatch.setattr(rq, "project_brand", lambda *a: "synthetic")
    captured = []
    def refresh(model):
        model.id = uuid.uuid4()
    db.refresh.side_effect = refresh
    def register(*args, **kw):
        assert db.commit.called
        assert db.refresh.called
        captured.append(kw)
    monkeypatch.setattr(review_bridge, "register_request", register)
    monkeypatch.setattr(settings, "review_engine", "continuity-v1")
    result = rq.create_request(rq.RequestCreate(project_id=project.id, title="Test"), db, user)
    assert captured == [{"tenant_id": f"freeframe:project:{project.id}", "request_id": result["id"], "engine": "continuity-v1"}]
    assert any(isinstance(call.args[0], UploadRequest) for call in db.add.call_args_list)


def test_invalid_server_configuration_preserves_request_but_surfaces_unavailable(monkeypatch):
    from apps.api.routers import requests as rq
    from apps.api.models.project import Project
    project = Project(id=uuid.uuid4(), name="Synthetic", created_by=uuid.uuid4())
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = project
    db.refresh.side_effect = lambda r: setattr(r, "id", uuid.uuid4())
    monkeypatch.setattr(rq, "require_project_role", lambda *a: None)
    monkeypatch.setattr(rq, "project_brand", lambda *a: "synthetic")
    monkeypatch.setattr(settings, "review_engine", "invalid")
    monkeypatch.setattr(review_bridge, "_call", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("fallback must not register")))
    result = rq.create_request(rq.RequestCreate(project_id=project.id, title="Test"), db, MagicMock(id=uuid.uuid4()))
    assert db.commit.called
    assert result["status"] == "unavailable"
