"""Actual staged upload/version/completion writes; no real storage or reviewer calls."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(not os.getenv('ITERATIONS_TEST_DATABASE_URL'), reason='opt-in local PostgreSQL check')


def test_staged_revision_history_and_serialized_completion(monkeypatch):
    from apps.api.database import Base
    from apps.api.models import User, Project, Folder, UploadRequest, Asset, AssetVersion, RequestUpload, MediaFile
    from apps.api.models.asset import ProcessingStatus
    from apps.api.routers import requests as rq
    admin = create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'])
    schema = 'editor_test_' + uuid.uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'], connect_args={'options': f'-csearch_path={schema}'})
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(rq, 'upload_guard_error', lambda *a: None)
    monkeypatch.setattr(rq, 'create_multipart_upload', lambda *a: 'multipart')
    monkeypatch.setattr(rq, 'complete_multipart_upload', lambda *a: None)
    monkeypatch.setattr(rq.s3_service, 'get_s3_client', lambda: MagicMock(head_object=lambda **k: {'ContentLength': 100}))
    monkeypatch.setattr(rq.s3_service, 'generate_presigned_get_url', lambda key: 'https://media.example/' + key)
    stats = {}
    monkeypatch.setattr(rq.review_bridge, 'asset_stats', lambda *a: stats)
    monkeypatch.setattr(rq.review_bridge, 'request_status', lambda *a: {'share': {'status': 'clear', 'openMustFixes': 0}})
    try:
        Base.metadata.create_all(engine)
        with Session() as db:
            owner = User(email='owner@example.test', name='Owner'); db.add(owner); db.flush()
            project = Project(name='Brand', created_by=owner.id); db.add(project); db.flush()
            folder = Folder(name='Hand in', project_id=project.id, created_by=owner.id); db.add(folder); db.flush()
            req = UploadRequest(token='token', review_share_token='share', title='Launch', project_id=project.id, folder_id=folder.id, created_by=owner.id)
            db.add(req); db.commit()
            init = rq.guest_initiate('token', rq.GuestInitiate(original_filename='cut.mp4', mime_type='video/mp4', file_size_bytes=100), db)
            assert db.query(RequestUpload).count() == 0
            with pytest.raises(HTTPException) as missing:
                rq.guest_complete('token', rq.GuestComplete(s3_key=init['s3_key'], upload_id='multipart', parts=[]), BackgroundTasks(), db)
            assert missing.value.status_code == 422
            db.rollback()
            rq.guest_complete('token', rq.GuestComplete(s3_key=init['s3_key'], upload_id='multipart', parts=[], name='Jamie', email='jamie@example.com'), BackgroundTasks(), db)
            assert db.query(RequestUpload).one().uploader_name == 'Jamie'
            assert db.query(RequestUpload).one().submitted_at is not None
            v1 = db.get(AssetVersion, uuid.UUID(init['version_id'])); v1.processing_status = ProcessingStatus.ready
            db.query(MediaFile).filter_by(version_id=v1.id).one().s3_key_processed = 'hls/prefix-not-an-object/'
            db.commit()
            stats[init['asset_id']] = {'version_id': init['version_id'], 'reviewed': True, 'openMustFix': 0}
            revision = rq.guest_initiate('token', rq.GuestInitiate(asset_id=init['asset_id'], original_filename='entirely-renamed-v2.mp4', mime_type='video/mp4', file_size_bytes=100, name='Jamie', email='jamie@example.com'), db)
            assert revision['asset_id'] == init['asset_id'] and revision['version_number'] == 2
            assert db.query(Asset).count() == 1
            # Complete holds the same row lock as finish until submitted bytes are committed.
            completing, allow_complete, trying_finish = Event(), Event(), Event()
            def store(*args):
                completing.set(); assert allow_complete.wait(5)
            monkeypatch.setattr(rq, 'complete_multipart_upload', store)
            def complete_revision():
                with Session() as other:
                    return rq.guest_complete('token', rq.GuestComplete(s3_key=revision['s3_key'], upload_id='multipart', parts=[]), BackgroundTasks(), other)
            def finish_during_complete():
                trying_finish.set()
                with Session() as other:
                    with pytest.raises(HTTPException) as blocked: rq.finish_request('token', other)
                    return blocked.value.status_code
            with ThreadPoolExecutor(max_workers=2) as pool:
                stored = pool.submit(complete_revision)
                assert completing.wait(5)
                closing = pool.submit(finish_during_complete)
                assert trying_finish.wait(5)
                allow_complete.set()
                assert stored.result(5)['version_id'] == revision['version_id']
                assert closing.result(5) == 409
            db.expire_all()
            review = rq.guest_review('token', db)
            assert review['assets'][0]['version_id'] == revision['version_id']
            assert review['assets'][0]['comments'] == [] and review['gate']['status'] == 'reviewing'
            old = rq.guest_version('token', uuid.UUID(init['asset_id']), uuid.UUID(init['version_id']), db)
            assert init['version_id'] in old['media_url']
            with pytest.raises(HTTPException): rq.finish_request('token', db)
            db.rollback()
            v2 = db.get(AssetVersion, uuid.UUID(revision['version_id']))
            v2.processing_status = ProcessingStatus.failed; db.commit()
            failed = rq.guest_review('token', db)
            assert failed['assets'][0]['version_id'] == revision['version_id']
            assert failed['gate']['status'] == 'unavailable'
            assert rq.list_requests(None, db, owner)[0]['status'] == 'unavailable'
            v2.processing_status = ProcessingStatus.ready; db.commit()
            stats[init['asset_id']] = {'version_id': revision['version_id'], 'reviewed': True, 'openMustFix': 0}
            abandoned = rq.guest_initiate('token', rq.GuestInitiate(original_filename='cancelled.mp4', mime_type='video/mp4', file_size_bytes=100), db)
            monkeypatch.setattr(rq, 'abort_multipart_upload', lambda *a: None)
            rq.guest_abort('token', rq.GuestPart(s3_key=abandoned['s3_key'], upload_id='multipart', part_number=1), db)
            assert len(rq.view_request('token', db)['assets']) == 1
        # A simultaneous initiation waits for the completion lock, then sees completed_at.
        checking, release = Event(), Event()
        def evidence(*args):
            checking.set(); assert release.wait(5); return stats
        monkeypatch.setattr(rq.review_bridge, 'asset_stats', evidence)
        def finish():
            with Session() as db: return rq.finish_request('token', db)
        def initiate():
            with Session() as db:
                with pytest.raises(HTTPException) as closed:
                    rq.guest_initiate('token', rq.GuestInitiate(original_filename='late.mp4', mime_type='video/mp4', file_size_bytes=100), db)
                return closed.value.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            finished = pool.submit(finish)
            assert checking.wait(5)
            late = pool.submit(initiate)
            release.set()
            assert finished.result(5)['completion_versions'] == {init['asset_id']: revision['version_id']}
            assert late.result(5) == 409
        with Session() as db:
            assert rq.view_request('token', db)['completed_at']
            assert db.query(Asset).count() == 2  # cancelled history preserved, excluded from completion
    finally:
        engine.dispose()
        with admin.begin() as conn: conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()
