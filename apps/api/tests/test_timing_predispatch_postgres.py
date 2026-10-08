"""Actual local PostgreSQL pre-dispatch authority, never providers or production."""
import os
import uuid

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import text

from apps.api.tests.test_timing_provenance_postgres import timing_pg, intent, initiate, complete
from apps.api.tests.test_timing_exclusion_postgres import natural, admission

pytestmark = pytest.mark.skipif(not os.getenv('TIMING_TEST_DATABASE_URL'), reason='opt-in disposable PostgreSQL')
AUTH = {'authorization': 'Bearer LOCAL-bridge'}


def legacy_version(a):
    from apps.api.models import Asset, AssetVersion
    from apps.api.models.asset import AssetType, ProcessingStatus
    with a.Session() as db:
        asset = Asset(project_id=a.project.id, folder_id=a.folder.id, name='LOCAL legacy.mp4', asset_type=AssetType.video, created_by=a.owner.id)
        db.add(asset); db.flush()
        version = AssetVersion(asset_id=asset.id, version_number=1, created_by=a.owner.id, processing_status=ProcessingStatus.ready)
        db.add(version); db.commit()
        return {'asset_id': str(asset.id), 'version_id': str(version.id)}


def legacy_admission(a, upload, **changes):
    return a.client.post('/internal/review/timing-legacy-exclusion', json={'share_token': 'share', 'asset_id':upload['asset_id'], 'version_id':upload['version_id'], **changes}, headers=AUTH)


def test_legacy_without_request_gets_durable_exact_negative_before_dispatch(timing_pg):
    from apps.api.models import AssetVersion, RequestUpload
    from apps.api.services.review_timing import freeze_submission_timing
    from apps.api.routers.requests import locked_request
    a = timing_pg; upload = legacy_version(a)
    response = legacy_admission(a, upload)
    assert response.status_code == 200, response.text
    assert response.json() == {'schema_version': 'autoreview.timing-admission.v1', 'tenant_id': str(a.project.id), 'share_token': 'share',
        **upload, 'version_number': 1, 'provenance': 'unknown'}
    assert response.headers['cache-control'] == 'private, no-store'
    with a.Session() as db:
        version = db.get(AssetVersion, uuid.UUID(upload['version_id'])); before = version.timing_exclusion
        assert before['upload_request_id'] is None and before['submitted_at'] is None
    a.engine.dispose()
    assert legacy_admission(a, upload).json() == response.json()
    # A later adoption/source cannot launder already-reviewed physical bytes.
    assert intent(a).status_code == 200
    with a.Session() as db:
        req = locked_request(db, a.req.id)
        version = db.get(AssetVersion, uuid.UUID(upload['version_id']))
        record = RequestUpload(request_id=req.id, asset_id=version.asset_id, version_number=1,
            uploader_name='LOCAL editor', uploader_email='editor@example.test')
        db.add(record); freeze_submission_timing(db, req, record, version); db.commit()
        assert version.timing_exclusion == before
    assert admission(a, upload).json()['provenance'] == 'unknown'


def test_immutable_unclassified_source_can_run_legacy_without_positive_clock(timing_pg):
    a = timing_pg; upload = initiate(a); complete(a, upload)
    response = legacy_admission(a, upload)
    assert response.status_code == 200, response.text
    assert response.json()['provenance'] == 'unclassified'
    assert 'submitted_at' not in response.json() and 'provenance_attestation' not in response.json()
    assert intent(a).status_code == 200
    assert admission(a, upload).json()['provenance'] == 'unclassified'


@pytest.mark.parametrize('kind', ['natural', 'pending', 'corrupt', 'ambiguous'])
def test_missing_metadata_is_not_permanent_negative_proof(timing_pg, kind):
    from apps.api.models import RequestUpload
    a = timing_pg; upload = natural(a) if kind in ('natural', 'corrupt', 'ambiguous') else initiate(a)
    if kind == 'corrupt':
        # Simulate pre-existing corrupt historical evidence without bypassing runtime protection.
        with a.engine.begin() as db:
            db.execute(text('ALTER TABLE request_uploads DISABLE TRIGGER protect_submission_timing'))
            db.execute(text("UPDATE request_uploads SET timing_provenance='{}'::jsonb"))
            db.execute(text('ALTER TABLE request_uploads ENABLE TRIGGER protect_submission_timing'))
    if kind == 'ambiguous':
        with a.Session() as db:
            record = db.query(RequestUpload).one()
            db.add(RequestUpload(request_id=record.request_id, asset_id=record.asset_id, version_number=record.version_number,
                submitted_at=record.submitted_at, uploader_name='LOCAL duplicate', uploader_email='duplicate@example.test')); db.commit()
    response = legacy_admission(a, upload)
    assert response.status_code == 409, response.text
    with a.Session() as db:
        from apps.api.models import AssetVersion
        assert db.get(AssetVersion, uuid.UUID(upload['version_id'])).timing_exclusion is None


def test_confirmed_test_negative_can_run_legacy_even_if_positive_context_missing(timing_pg):
    a = timing_pg; upload = natural(a)
    assert admission(a, upload, 'operator-test').status_code == 200
    assert legacy_admission(a, upload).json()['provenance'] == 'operator-test'


def test_legacy_authority_rejects_wrong_scope_and_read_only_key(timing_pg):
    a = timing_pg; upload = legacy_version(a)
    response = a.client.post('/internal/review/timing-legacy-exclusion', json={'share_token': 'share', **upload}, headers={'X-API-Key':'LOCAL-read-key'})
    assert response.status_code == 401
    assert legacy_admission(a, upload, version_id=str(uuid.uuid4())).status_code == 404
    assert legacy_admission(a, upload, share_token='missing').status_code == 404
    from apps.api.models import ShareLink, Folder
    with a.Session() as db:
        folder = Folder(name='LOCAL other', project_id=a.project.id, created_by=a.owner.id)
        db.add(folder); db.flush(); db.add(ShareLink(token='other', folder_id=folder.id, created_by=a.owner.id)); db.commit()
    assert legacy_admission(a, upload, share_token='other').status_code == 403


@pytest.mark.skipif(not os.getenv('TIMING_WORKER_PATH'), reason='opt-in actual local Worker producer')
def test_actual_worker_producer_http_pg_disconnect_recovery_and_sticky_exclusion(timing_pg):
    import json
    import socket
    import subprocess
    import threading
    import time
    from pathlib import Path
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response
    from sqlalchemy.exc import DBAPIError
    from apps.api.database import get_db
    from apps.api.models import AssetVersion
    from apps.api.routers.review_timing import router
    from apps.api.tests.test_timing_provenance_postgres import context
    a = timing_pg; current = natural(a)
    state = {'outage': False, 'pg_disconnects': 0, 'media_reads': 0, 'comments': []}
    app = FastAPI(); app.include_router(router)
    def database():
        with a.Session() as db:
            if state['outage']:
                # Real PostgreSQL connection loss, not a mocked admission result.
                db.execute(text('SELECT pg_terminate_backend(pg_backend_pid())'))
            yield db
    app.dependency_overrides[get_db] = database
    @app.exception_handler(DBAPIError)
    async def disconnected(request, exc):
        state['pg_disconnects'] += 1
        return JSONResponse({'detail':'LOCAL PostgreSQL disconnect'}, status_code=503)
    @app.get('/local-state')
    def local_state():
        with a.Session() as db:
            exclusion = db.get(AssetVersion, uuid.UUID(current['version_id'])).timing_exclusion
        return {**state, 'asset_id':current['asset_id'], 'version_id':current['version_id'], 'exclusion':exclusion}
    @app.post('/local-control')
    async def local_control(request: Request):
        nonlocal current
        body = await request.json()
        if 'outage' in body: state['outage'] = body['outage']
        if body.get('new_version'):
            current = initiate(a, current['asset_id']); complete(a, current)
        return {'asset_id':current['asset_id'], 'version_id':current['version_id']}
    @app.get('/share/share')
    def capability(): return {'permission':'comment', 'allow_download':True, 'folder_name':'LOCAL', 'folder_id':str(a.folder.id)}
    @app.get('/share/share/assets')
    def assets():
        with a.Session() as db: number = db.get(AssetVersion, uuid.UUID(current['version_id'])).version_number
        return [{'id':current['asset_id'], 'name':'LOCAL cut.mp4', 'asset_type':'video', 'duration_seconds':240, 'version_count':number}]
    @app.get('/share/share/stream/{asset_id}')
    def media_context(asset_id: str, request: Request):
        assert asset_id == current['asset_id']
        return {'url':str(request.base_url)+'local-media/'+current['version_id'], 'version_id':current['version_id'], **context(a,current)}
    @app.api_route('/local-media/{version_id}', methods=['GET','HEAD'])
    def local_media(version_id: str):
        assert version_id == current['version_id']
        state['media_reads'] += 1
        return Response(b'\x00\x00\x00\x18', media_type='video/mp4')
    @app.post('/share/share/comment')
    async def comment(request: Request):
        body = await request.json(); state['comments'].append(body)
        return JSONResponse({'id':'c'+str(len(state['comments']))}, status_code=201)
    worker = Path(os.environ['TIMING_WORKER_PATH'])
    node = os.environ.get('TIMING_NODE_PATH','/Users/alansimon/.nvm/versions/node/v22.22.3/bin/node')
    sock=socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',lifespan='off'))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True); thread.start()
    try:
        deadline=time.monotonic()+5
        while not server.started and time.monotonic()<deadline: time.sleep(.01)
        assert server.started
        result=subprocess.run([node,str(worker/'node_modules/vitest/vitest.mjs'),'run','test/timing-predispatch-http.test.ts','--maxWorkers=1','--minWorkers=1'],
            cwd=worker,env={**os.environ,'TIMING_PREDISPATCH_HTTP_BASE':f'http://127.0.0.1:{port}'},capture_output=True,text=True,timeout=45)
        print(result.stdout)
        assert result.returncode==0,result.stdout+result.stderr
    finally:
        server.should_exit=True;thread.join(5);sock.close()
        assert not thread.is_alive()
