"""Synthetic disposable PostgreSQL only; real commits/row locks, no providers/storage."""
import importlib.util
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(not os.getenv('TIMING_TEST_DATABASE_URL'), reason='opt-in disposable PostgreSQL')
MIGRATION = Path(__file__).parents[1] / 'alembic/versions/e1d8a10b2026_submission_timing_provenance.py'


def migration():
    spec = importlib.util.spec_from_file_location('timing_migration', MIGRATION)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


@pytest.fixture
def timing_pg(monkeypatch, client):
    from apps.api.config import settings
    from apps.api.database import Base, get_db
    from apps.api.main import app
    from apps.api.models import User, Project, Folder, UploadRequest, ShareLink
    from apps.api.routers import requests as rq
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    url = os.environ['TIMING_TEST_DATABASE_URL']
    assert 'freeframe_h3_test' in url and ('127.0.0.1' in url or 'localhost' in url)
    schema = 'timing_' + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection: connection.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    if MIGRATION.exists():
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE upload_requests DROP COLUMN IF EXISTS timing_natural_intent; ALTER TABLE request_uploads DROP COLUMN IF EXISTS timing_provenance'))
            with Operations.context(MigrationContext.configure(connection)): migration().upgrade()
    exclusion = MIGRATION.with_name('f1d8a10b2026_timing_test_exclusion.py')
    if exclusion.exists():
        spec = importlib.util.spec_from_file_location('exclusion_migration', exclusion)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE upload_requests DROP COLUMN IF EXISTS timing_run_purpose; ALTER TABLE asset_versions DROP COLUMN IF EXISTS timing_exclusion'))
            with Operations.context(MigrationContext.configure(connection)): module.upgrade()
    monkeypatch.setattr(settings, 'review_bridge_secret', 'LOCAL-bridge')
    monkeypatch.setattr(settings, 'service_api_key', 'LOCAL-read-key')
    monkeypatch.setattr(settings, 'service_api_key_email', 'service@example.test')
    monkeypatch.setattr(rq, 'upload_guard_error', lambda *a: None)
    monkeypatch.setattr(rq, 'create_multipart_upload', lambda *a: 'multipart')
    monkeypatch.setattr(rq, 'complete_multipart_upload', lambda *a: None)
    monkeypatch.setattr(rq.s3_service, 'get_s3_client', lambda: MagicMock(head_object=lambda **k: {'ContentLength': 100}))
    def database():
        with Session() as db: yield db
    app.dependency_overrides[get_db] = database
    with Session() as db:
        owner = User(email='owner@example.test', name='LOCAL owner'); db.add(owner); db.flush()
        project = Project(name='LOCAL project', created_by=owner.id); db.add(project); db.flush()
        folder = Folder(name='Assignment', project_id=project.id, created_by=owner.id); db.add(folder); db.flush()
        req = UploadRequest(token='upload', review_share_token='share', title='LOCAL order', project_id=project.id, folder_id=folder.id, created_by=owner.id)
        db.add_all([req, ShareLink(token='share', folder_id=folder.id, created_by=owner.id)]); db.commit()
    a = SimpleNamespace(Session=Session, engine=engine, req=req, owner=owner, project=project, folder=folder, client=client)
    try: yield a
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
        with admin.begin() as connection: connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def intent(a, *, apply=True, **changes):
    payload = {'project_id': str(a.project.id), 'share_token': 'share', **changes}
    path = f'/internal/review/timing-intent/{a.req.id}'
    headers = {'authorization': 'Bearer LOCAL-bridge'}
    if apply: return a.client.post(path, json={**payload, 'customer_order_verified': True}, headers=headers)
    return a.client.get(path, params=payload, headers=headers)


def initiate(a, asset_id=None):
    from apps.api.routers import requests as rq
    with a.Session() as db:
        return rq.guest_initiate('upload', rq.GuestInitiate(original_filename='cut.mp4', mime_type='video/mp4', file_size_bytes=100,
            asset_id=asset_id, name='LOCAL editor', email='editor@example.com'), db)


def complete(a, upload):
    from apps.api.routers import requests as rq
    with a.Session() as db:
        return rq.guest_complete('upload', rq.GuestComplete(s3_key=upload['s3_key'], upload_id='multipart', parts=[]), BackgroundTasks(), db)


def context(a, upload, db=None):
    from apps.api.services.review_timing import private_timing_context
    def read(session):
        return private_timing_context(session, 'LOCAL-read-key', 'share', uuid.UUID(upload['asset_id']), uuid.UUID(upload['version_id']),
            a.project.id, service_user=SimpleNamespace(email='service@example.test'))
    if db: return read(db)
    with a.Session() as session: return read(session)


def assert_lock_wait(a):
    # Observe a real blocked PostgreSQL statement instead of assuming thread scheduling.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with a.engine.connect() as connection:
            if connection.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'")).scalar(): return
        time.sleep(.01)
    pytest.fail('second transaction did not wait for the real row lock')


def test_v1_cannot_be_promoted_by_later_attestation_and_v2_freezes_natural(timing_pg):
    from apps.api.models import RequestUpload, UploadRequest
    a = timing_pg; v1 = initiate(a); complete(a, v1)
    response = intent(a, apply=False); assert response.status_code == 200, response.text
    with a.Session() as db: assert db.get(UploadRequest, a.req.id).timing_natural_intent is None
    first = context(a, v1)['timing_context']['submission_provenance']
    assert first['provenance'] == 'unclassified'
    response = intent(a); assert response.status_code == 200, response.text
    attested = response.json()['attested_at']
    assert intent(a).json()['attested_at'] == attested
    assert context(a, v1)['timing_context']['submission_provenance'] == first
    v2 = initiate(a, v1['asset_id']); complete(a, v2)
    second = context(a, v2)['timing_context']['submission_provenance']
    assert second['provenance'] == 'natural' and second['version_id'] == v2['version_id']
    assert second['upload_request_id'] == str(a.req.id)
    assert datetime.fromisoformat(attested) < datetime.fromisoformat(second['submitted_at'])
    complete(a, v2)
    assert context(a, v2)['timing_context']['submission_provenance'] == second
    with a.Session() as db: assert db.query(RequestUpload).count() == 2


@pytest.mark.parametrize('first', ['submission', 'attestation'])
def test_actual_transactions_serialize_both_race_orders(timing_pg, first):
    from apps.api.routers.requests import locked_request
    from apps.api.services.review_timing import attest_request_timing
    from apps.api.models import UploadRequest
    a = timing_pg; upload = initiate(a)
    with a.Session() as holding, ThreadPoolExecutor(max_workers=1) as pool:
        locked_request(holding, a.req.id)
        if first == 'submission':
            future = pool.submit(lambda: intent(a))
            try:
                assert_lock_wait(a)
                from apps.api.routers import requests as rq
                rq.guest_complete('upload', rq.GuestComplete(s3_key=upload['s3_key'], upload_id='multipart', parts=[]), BackgroundTasks(), holding)
            finally: holding.rollback()
            assert future.result(5).status_code == 200
        else:
            attest_request_timing(holding, a.req.id, a.project.id, 'share', apply=True)
            future = pool.submit(lambda: complete(a, upload))
            try: assert_lock_wait(a); holding.commit()
            finally: holding.rollback()
            assert future.result(5)['version_id'] == upload['version_id']
    expected = 'unclassified' if first == 'submission' else 'natural'
    assert context(a, upload)['timing_context']['submission_provenance']['provenance'] == expected


def test_rolled_back_intent_and_submission_do_not_establish_evidence(timing_pg):
    from apps.api.routers import requests as rq
    from apps.api.services.review_timing import attest_request_timing, freeze_submission_timing
    from apps.api.models import UploadRequest, AssetVersion, RequestUpload
    a = timing_pg; upload = initiate(a)
    with a.Session() as db:
        attest_request_timing(db, a.req.id, a.project.id, 'share', apply=True); db.rollback()
        assert db.get(UploadRequest, a.req.id).timing_natural_intent is None
        req = rq.locked_request(db, a.req.id)
        version = db.get(AssetVersion, uuid.UUID(upload['version_id']))
        record = db.query(RequestUpload).one()
        freeze_submission_timing(db, req, record, version); db.flush(); db.rollback()
        assert db.query(RequestUpload).one().submitted_at is None
    complete(a, upload)
    assert context(a, upload)['timing_context']['submission_provenance']['provenance'] == 'unclassified'


@pytest.mark.parametrize('other_order', [False, True])
def test_ambiguous_exact_sources_and_other_scope_have_no_private_context(timing_pg, other_order):
    from apps.api.models import RequestUpload, UploadRequest
    a = timing_pg; assert intent(a).status_code == 200
    upload = initiate(a); complete(a, upload)
    with a.Session() as db:
        original = db.query(RequestUpload).one()
        request_id = a.req.id
        if other_order:
            other = UploadRequest(token='other-upload', review_share_token='share', title='LOCAL second order', project_id=a.project.id, folder_id=a.folder.id, created_by=a.owner.id)
            db.add(other); db.flush(); request_id = other.id
        # Legal historical duplicate; never take .first() or borrow another U's evidence.
        db.add(RequestUpload(request_id=request_id, asset_id=original.asset_id, version_number=1,
            submitted_at=original.submitted_at, uploader_name='LOCAL duplicate', uploader_email='duplicate@example.test'))
        db.commit()
    assert context(a, upload) == {}
    assert intent(a, project_id=str(uuid.uuid4())).status_code == 404
    assert intent(a, share_token='other').status_code == 404


def test_database_rejects_backfill_and_changes_to_committed_clock(timing_pg):
    from sqlalchemy.exc import DBAPIError
    from apps.api.models import RequestUpload
    a = timing_pg; upload = initiate(a); complete(a, upload)
    with a.Session() as db:
        record = db.query(RequestUpload).one(); before = record.timing_provenance
        record.timing_provenance = {**before, 'provenance': 'natural'}
        with pytest.raises(DBAPIError): db.commit()
        db.rollback(); record = db.query(RequestUpload).one(); record.submitted_at = datetime.now(timezone.utc)
        with pytest.raises(DBAPIError): db.commit()
        db.rollback()
        db.execute(text('INSERT INTO request_uploads (id,request_id,asset_id,version_number,submitted_at,uploader_name,uploader_email) VALUES (:id,:request,:asset,99,clock_timestamp(),\'legacy\',\'legacy@example.test\')'),
            {'id': uuid.uuid4(), 'request': a.req.id, 'asset': uuid.UUID(upload['asset_id'])}); db.commit()
        old = db.query(RequestUpload).filter_by(version_number=99).one(); old.timing_provenance = before
        with pytest.raises(DBAPIError): db.commit()


def test_migration_downgrade_reupgrade_preserves_historical_unknown(timing_pg):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    a = timing_pg; upload = initiate(a); complete(a, upload)
    with a.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration().downgrade(); migration().upgrade()
        assert connection.execute(text('SELECT timing_provenance FROM request_uploads')).scalar() is None
    assert context(a, upload)['timing_context']['submission_provenance']['provenance'] == 'unclassified'


@pytest.mark.parametrize('headers', [{}, {'x-api-key': 'LOCAL-read-key'}, {'authorization': 'Bearer normal-owner-token'}, {'authorization': 'Bearer wrong'}])
def test_guests_owners_and_read_only_keys_cannot_attest(timing_pg, headers):
    a = timing_pg
    payload = {'project_id': str(a.project.id), 'share_token': 'share', 'customer_order_verified': True}
    path = f'/internal/review/timing-intent/{a.req.id}'
    assert a.client.post(path, json=payload, headers=headers).status_code == 401
    assert a.client.get(path, params={k: v for k, v in payload.items() if k != 'customer_order_verified'}, headers=headers).status_code == 401


@pytest.mark.parametrize('change', [{'attested_at': '2000-01-01T00:00:00Z'}, {'customer_order_verified': False}, {'provenance': 'natural'}])
def test_service_cannot_backdate_or_apply_unverified_intent(timing_pg, change):
    a = timing_pg
    payload = {'project_id': str(a.project.id), 'share_token': 'share', 'customer_order_verified': True, **change}
    assert a.client.post(f'/internal/review/timing-intent/{a.req.id}', json=payload, headers={'authorization': 'Bearer LOCAL-bridge'}).status_code == 422


def test_guest_payload_cannot_set_origin_and_guest_view_contains_no_private_fields(timing_pg):
    from apps.api.routers import requests as rq
    a = timing_pg
    with a.Session() as db:
        upload = rq.guest_initiate('upload', rq.GuestInitiate(original_filename='cut.mp4', mime_type='video/mp4', file_size_bytes=100,
            name='LOCAL editor', email='editor@example.com', timing_natural_intent={'provenance': 'natural'}), db)
        rq.guest_complete('upload', rq.GuestComplete(s3_key=upload['s3_key'], upload_id='multipart', parts=[],
            timing_provenance={'provenance': 'natural'}), BackgroundTasks(), db)
    assert context(a, upload)['timing_context']['submission_provenance']['provenance'] == 'unclassified'
    response = a.client.get('/r/upload'); assert response.status_code == 200
    assert not any(k in response.text for k in ('timing_natural_intent', 'timing_provenance', 'submission_provenance', 'attested_at'))


def test_internal_adoption_never_promotes_existing_media(timing_pg):
    from apps.api.models import Asset, AssetVersion, ShareLink, ProjectMember
    from apps.api.models.asset import AssetType, ProcessingStatus
    from apps.api.models.project import ProjectRole
    from apps.api.models.share import SharePermission
    from apps.api.routers import requests as rq
    a = timing_pg; assert intent(a).status_code == 200
    with a.Session() as db:
        project = db.get(type(a.project), a.project.id); project.is_workspace = True
        folder = db.get(type(a.folder), a.folder.id); folder.description = 'https://trello.com/c/AbCdEf12'
        owner = db.get(type(a.owner), a.owner.id); owner.is_staff = True
        db.add(ProjectMember(project_id=project.id, user_id=owner.id, role=ProjectRole.owner))
        share = db.query(ShareLink).one(); share.title = 'Auto Review'; share.permission = SharePermission.comment
        asset = Asset(project_id=project.id, folder_id=folder.id, name='LOCAL old file', asset_type=AssetType.video, created_by=owner.id)
        db.add(asset); db.flush()
        version = AssetVersion(asset_id=asset.id, version_number=1, processing_status=ProcessingStatus.ready, created_by=owner.id)
        db.add(version); db.commit()
        rq.folder_editor_request(folder.id, db, owner)
        upload = {'asset_id': str(asset.id), 'version_id': str(version.id)}
    assert context(a, upload)['timing_context']['submission_provenance']['provenance'] == 'unclassified'
