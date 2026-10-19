"""POST /integrations/portal/delivery-folder: the portal's server-to-server hand-in endpoint.

Real-Postgres (via the `real_db` fixture) because the endpoint's whole point is idempotent
find-or-create across folder + share + request - exactly the kind of multi-row interaction a
hand-mocked Session hides bugs in.
"""
import hashlib
import hmac
import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.models.folder import Folder
from apps.api.models.project import Project
from apps.api.models.share import ShareLink, SharePermission
from apps.api.models.upload_request import UploadRequest
from apps.api.models.user import User
from apps.api.routers.portal import router

SECRET = "portal-test-secret"
CARD_URL = "https://trello.com/c/AbCd1234"


@pytest.fixture
def portal_app(real_db, monkeypatch):
    monkeypatch.setattr(settings, "portal_freeframe_hmac_secret", SECRET)
    monkeypatch.setattr(settings, "frontend_url", "https://feedback.example.test")
    service = User(email=f"portal-service-{uuid.uuid4()}@example.test", name="Portal Service", is_staff=True)
    real_db.add(service)
    real_db.flush()
    monkeypatch.setattr(settings, "portal_freeframe_service_email", service.email)
    project = Project(name="Brand workspace", is_workspace=True, created_by=service.id)
    real_db.add(project)
    real_db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: real_db
    with TestClient(app) as client:
        yield client, real_db, project, service


def _post(client, payload, secret=SECRET):
    body = json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json"}
    if secret is not None:
        headers["X-Aditor-Signature"] = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return client.post("/integrations/portal/delivery-folder", content=body, headers=headers)


def test_missing_signature_is_401(portal_app):
    client, _db, project, _service = portal_app
    response = _post(client, {"card_url": CARD_URL, "workspace_project_id": str(project.id)}, secret=None)
    assert response.status_code == 401


def test_wrong_signature_is_401(portal_app):
    client, _db, project, _service = portal_app
    response = _post(client, {"card_url": CARD_URL, "workspace_project_id": str(project.id)}, secret="not-the-secret")
    assert response.status_code == 401


def test_unconfigured_secret_fails_closed(portal_app, monkeypatch):
    client, _db, project, _service = portal_app
    monkeypatch.setattr(settings, "portal_freeframe_hmac_secret", "")
    response = _post(client, {"card_url": CARD_URL, "workspace_project_id": str(project.id)})
    assert response.status_code == 401


def test_malformed_card_url_is_400(portal_app):
    client, _db, project, _service = portal_app
    response = _post(client, {"card_url": "https://trello.com/boards/not-a-card", "workspace_project_id": str(project.id)})
    assert response.status_code == 400


def test_unknown_workspace_is_404(portal_app):
    client, _db, _project, _service = portal_app
    response = _post(client, {"card_url": CARD_URL, "workspace_project_id": str(uuid.uuid4())})
    assert response.status_code == 404


def test_misconfigured_service_account_is_503(portal_app, monkeypatch):
    client, _db, project, _service = portal_app
    monkeypatch.setattr(settings, "portal_freeframe_service_email", "")
    response = _post(client, {"card_url": CARD_URL, "workspace_project_id": str(project.id)})
    assert response.status_code == 503


def test_first_call_creates_folder_request_and_share_attributed_to_the_service_account(portal_app):
    client, db, project, service = portal_app
    response = _post(client, {"card_url": CARD_URL, "workspace_project_id": str(project.id), "title": "Spring launch"})
    assert response.status_code == 200
    out = response.json()
    assert out["upload_url"] == f"https://feedback.example.test/r/{out['token']}"
    assert out["review_url"] == f"https://feedback.example.test/share/{out['review_share_token']}"

    folder = db.query(Folder).filter(Folder.id == uuid.UUID(out["folder_id"])).one()
    assert folder.project_id == project.id
    assert folder.name == "Spring launch"
    assert folder.description == CARD_URL
    assert folder.created_by == service.id

    req = db.query(UploadRequest).filter(UploadRequest.folder_id == folder.id).one()
    assert req.token == out["token"]
    assert req.created_by == service.id
    assert req.review_share_token == out["review_share_token"]

    share = db.query(ShareLink).filter(ShareLink.folder_id == folder.id).one()
    assert share.token == out["review_share_token"]
    assert share.permission == SharePermission.comment
    assert share.allow_download is True
    assert share.created_by == service.id


def test_a_folder_with_no_title_is_named_after_the_card_key(portal_app):
    client, db, project, _service = portal_app
    response = _post(client, {"card_url": CARD_URL, "workspace_project_id": str(project.id)})
    folder = db.query(Folder).filter(Folder.id == uuid.UUID(response.json()["folder_id"])).one()
    assert folder.name == "AbCd1234"


def test_two_calls_for_the_same_card_are_idempotent(portal_app):
    client, db, project, _service = portal_app
    payload = {"card_url": CARD_URL, "workspace_project_id": str(project.id), "title": "Spring launch"}
    first = _post(client, payload).json()
    second = _post(client, payload).json()

    assert first == second
    assert db.query(Folder).filter(Folder.project_id == project.id).count() == 1
    assert db.query(UploadRequest).filter(UploadRequest.folder_id == uuid.UUID(first["folder_id"])).count() == 1
    assert db.query(ShareLink).filter(ShareLink.folder_id == uuid.UUID(first["folder_id"])).count() == 1


def test_reuses_a_folder_the_interactive_handin_flow_already_created_for_the_same_card(portal_app):
    client, db, project, service = portal_app
    existing = Folder(project_id=project.id, name="Already filed", description=CARD_URL, created_by=service.id)
    db.add(existing)
    db.commit()

    response = _post(client, {"card_url": CARD_URL, "workspace_project_id": str(project.id)})
    assert response.status_code == 200
    assert response.json()["folder_id"] == str(existing.id)
    assert db.query(Folder).filter(Folder.project_id == project.id).count() == 1
