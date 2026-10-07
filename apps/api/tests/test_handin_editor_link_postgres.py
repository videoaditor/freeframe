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
