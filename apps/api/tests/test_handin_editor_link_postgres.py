"""Real persistence and scope for converting an internal hand-in to its native editor."""
import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(not os.getenv('ITERATIONS_TEST_DATABASE_URL'), reason='opt-in local PostgreSQL check')


@pytest.fixture
def handin_db(monkeypatch):
    from apps.api.database import Base
    from apps.api.config import settings
    from apps.api.models import User, Project, Folder
    from apps.api.models.project import ProjectMember, ProjectRole
    from apps.api.models.share import ShareLink, SharePermission
    admin = create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'])
    schema = 'native_handin_' + uuid.uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'], connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(settings, 'instance_wide_project_access', False)
    monkeypatch.setattr(settings, 'frontend_url', 'https://feedback.example.test')
    with Session() as db:
        owner = User(email='editor@example.test', name='Internal editor', is_staff=True)
        db.add(owner); db.flush()
        project = Project(name='Native brand', is_workspace=True, created_by=owner.id)
        db.add(project); db.flush()
        db.add(ProjectMember(project_id=project.id, user_id=owner.id, role=ProjectRole.owner))
        folder = Folder(project_id=project.id, name='Campaign', description='https://trello.com/c/AbCd1234', created_by=owner.id)
        db.add(folder); db.flush()
        share = ShareLink(folder_id=folder.id, created_by=owner.id, token='native-customer-share', title='Auto Review', permission=SharePermission.comment, allow_download=True)
        db.add(share); db.commit()
        yield db, owner, project, folder, share, Session
    engine.dispose()
    with admin.begin() as conn:
        conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    admin.dispose()


def test_internal_link_reuses_folder_and_exact_versions_on_retry(handin_db):
    from apps.api.routers.requests import folder_editor_request
    from apps.api.models.asset import Asset, AssetVersion, AssetType, ProcessingStatus
    from apps.api.models.upload_request import UploadRequest, RequestUpload
    db, owner, project, folder, share, _ = handin_db
    asset = Asset(project_id=project.id, folder_id=folder.id, name='Cut', asset_type=AssetType.video, created_by=owner.id)
    db.add(asset); db.flush()
    for n in (1, 2):
        db.add(AssetVersion(asset_id=asset.id, version_number=n, processing_status=ProcessingStatus.ready, created_by=owner.id))
    db.commit()
    first = folder_editor_request(folder.id, db, owner)
    again = folder_editor_request(folder.id, db, owner)
    assert first['url'] == again['url'] == f"https://feedback.example.test/r/{first['token']}"
    assert first['share_url'] == 'https://feedback.example.test/share/native-customer-share'
    assert db.query(UploadRequest).count() == 1
    records = db.query(RequestUpload).order_by(RequestUpload.version_number).all()
    assert [r.version_number for r in records] == [1, 2]
    assert all(r.submitted_at and r.uploader_email == owner.email for r in records)


def test_customer_cannot_convert_a_folder_into_an_internal_editor_link(handin_db):
    from apps.api.routers.requests import folder_editor_request
    from apps.api.models.upload_request import UploadRequest
    db, owner, _, folder, _, _ = handin_db
    owner.is_staff = False; db.commit()
    with pytest.raises(HTTPException) as error:
        folder_editor_request(folder.id, db, owner)
    assert error.value.status_code == 403
    assert db.query(UploadRequest).count() == 0


def test_revoked_editor_capability_is_never_recreated_by_handin_retry(handin_db):
    from apps.api.routers.requests import folder_editor_request
    from apps.api.models.upload_request import UploadRequest
    db, owner, _, folder, _, _ = handin_db
    result = folder_editor_request(folder.id, db, owner)
    request = db.query(UploadRequest).filter_by(token=result['token']).one()
    request.revoked_at = datetime.now(timezone.utc); db.commit()
    with pytest.raises(HTTPException) as error:
        folder_editor_request(folder.id, db, owner)
    assert error.value.status_code == 410
    assert db.query(UploadRequest).count() == 1


def test_foreign_workspace_membership_does_not_grant_editor_link(handin_db):
    from apps.api.routers.requests import folder_editor_request
    from apps.api.models.user import User
    db, _, _, folder, _, _ = handin_db
    outsider = User(email='outsider@example.test', name='Another editor', is_staff=True)
    db.add(outsider); db.commit()
    with pytest.raises(HTTPException) as error:
        folder_editor_request(folder.id, db, outsider)
    assert error.value.status_code == 403


def test_conflicting_request_project_is_not_adopted(handin_db):
    from apps.api.routers.requests import folder_editor_request
    from apps.api.models.upload_request import UploadRequest
    from apps.api.models.project import Project
    db, owner, project, folder, share, _ = handin_db
    other = Project(name='Other', created_by=owner.id, is_workspace=True)
    db.add(other); db.flush()
    db.add(UploadRequest(token='wrong-project',project_id=other.id,folder_id=folder.id,created_by=owner.id,title='Wrong',review_share_token=share.token)); db.commit()
    with pytest.raises(HTTPException) as error:
        folder_editor_request(folder.id,db,owner)
    assert error.value.status_code == 409


def test_internal_conversion_is_a_real_http_route(handin_db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.api.database import get_db
    from apps.api.middleware.auth import get_current_user
    from apps.api.routers.requests import router
    db, owner, _, folder, _, _ = handin_db
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        first = client.post(f'/folders/{folder.id}/editor-request')
        again = client.post(f'/folders/{folder.id}/editor-request')
    assert first.status_code == again.status_code == 200
    assert first.json()['url'] == again.json()['url']
    assert first.json()['share_url'].startswith('https://feedback.example.test/share/')


@pytest.mark.parametrize('change', ['disabled','expired','password','private'])
def test_protected_or_disabled_share_is_not_widened(handin_db,change):
    from apps.api.routers.requests import folder_editor_request
    db,owner,_,folder,share,_ = handin_db
    if change == 'disabled': share.is_enabled=False
    if change == 'expired': share.expires_at=datetime(2000,1,1,tzinfo=timezone.utc)
    if change == 'password': share.password_hash='existing-protection'
    if change == 'private': share.visibility='internal'
    db.commit()
    with pytest.raises(HTTPException) as error: folder_editor_request(folder.id,db,owner)
    assert error.value.status_code == 409


def test_private_editor_target_attests_only_live_exact_assignment(handin_db,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.api.config import settings
    from apps.api.database import get_db
    from apps.api.routers.requests import folder_editor_request
    from apps.api.routers.checklists import router
    from apps.api.models.upload_request import UploadRequest
    db,owner,_,folder,_,_=handin_db
    result=folder_editor_request(folder.id,db,owner)
    monkeypatch.setattr(settings,'review_bridge_secret','local-fixture-secret')
    app=FastAPI(); app.include_router(router); app.dependency_overrides[get_db]=lambda:db
    with TestClient(app) as client:
        path=f"/internal/review/editor-target/{result['token']}"
        assert client.get(path).status_code==401
        response=client.get(path,headers={'Authorization':'Bearer local-fixture-secret'})
        assert response.status_code==200
        assert response.json()['folder_id']==str(folder.id)
        assert response.json()['url']==result['url']
        assert response.headers['cache-control']=='private, no-store'
        req=db.query(UploadRequest).filter_by(token=result['token']).one()
        req.revoked_at=datetime.now(timezone.utc);db.commit()
        assert client.get(path,headers={'Authorization':'Bearer local-fixture-secret'}).status_code==404


def test_legacy_claim_serializes_conflicts_and_keeps_revoked_identity(handin_db,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.api.config import settings
    from apps.api.database import get_db
    from apps.api.routers.checklists import router
    from apps.api.models.upload_request import UploadRequest
    db,owner,project,folder,share,Session=handin_db
    for token in ('first-target','second-target'):
        db.add(UploadRequest(token=token,project_id=project.id,folder_id=folder.id,created_by=owner.id,title='Target',review_share_token=share.token))
    db.commit();monkeypatch.setattr(settings,'review_bridge_secret','local-fixture-secret')
    app=FastAPI();app.include_router(router)
    def session():
        with Session() as current:yield current
    app.dependency_overrides[get_db]=session
    def claim(token):
        with TestClient(app) as client:
            return client.post('/internal/review/editor-bindings',json={'legacy_ref':'u:old','token':token},headers={'Authorization':'Bearer local-fixture-secret'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(claim,('first-target','second-target')))
    assert sorted(r.status_code for r in responses)==[200,409]
    winner=('first-target','second-target')[next(i for i,r in enumerate(responses) if r.status_code==200)]
    assert claim(winner).status_code==200
    path='/internal/review/editor-bindings?legacy_ref=u:old'
    with TestClient(app) as client:
        assert client.get(path).status_code==401
        read=client.get(path,headers={'Authorization':'Bearer local-fixture-secret'})
        assert read.status_code==200 and read.json()['mapped'] is True
        assert read.json()['target']['token']==winner
        assert read.headers['cache-control']=='private, no-store'
        assert client.get('/internal/review/editor-bindings?legacy_ref=u:never-mapped',headers={'Authorization':'Bearer local-fixture-secret'}).json()=={'mapped':False}
    req=db.query(UploadRequest).filter_by(token=winner).one();req.revoked_at=datetime.now(timezone.utc);db.commit()
    assert claim('second-target' if winner=='first-target' else 'first-target').status_code==409
    with TestClient(app) as client:
        assert client.get(path,headers={'Authorization':'Bearer local-fixture-secret'}).status_code==410
