"""LOCAL true-PostgreSQL timing exclusion; no providers or customer data."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from apps.api.tests.test_timing_provenance_postgres import (
    timing_pg, intent, initiate, complete, context, assert_lock_wait)

pytestmark = pytest.mark.skipif(not __import__('os').getenv('TIMING_TEST_DATABASE_URL'), reason='opt-in disposable PostgreSQL')
AUTH = {'authorization': 'Bearer LOCAL-bridge'}


def purpose(a, value):
    return a.client.post('/internal/review/timing-purpose/share', json={'purpose': value}, headers=AUTH)


def admission(a, upload, reason=None, **change):
    body = dict(project_id=str(a.project.id), share_token='share', asset_id=upload['asset_id'], version_id=upload['version_id'], exclusion=reason)
    return a.client.post(f'/internal/review/timing-admission/{a.req.id}', json={**body, **change}, headers=AUTH)


def status(a, upload):
    with a.Session() as db:
        from apps.api.models import RequestUpload
        proof = db.query(RequestUpload).filter_by(asset_id=uuid.UUID(upload['asset_id']), version_number=1).first().timing_provenance
    body = {'versions': [dict(tenant_id=str(a.project.id), asset_id=upload['asset_id'], version_id=upload['version_id'], provenance_attestation=proof.get('provenance_attestation', 'a' * 64))]}
    return a.client.post('/internal/review/timing-status', json=body, headers=AUTH)


def natural(a):
    assert intent(a).status_code == 200
    upload = initiate(a); complete(a, upload)
    return upload


@pytest.mark.parametrize('patch,expected', [({'quiet': False}, 'synthetic'), ({'provenance': None}, 'operator-test')])
def test_partial_flags_preserve_other_durable_mode_for_future_submissions(timing_pg, patch, expected):
    a = timing_pg; assert intent(a).status_code == 200
    path = '/internal/review/timing-purpose/share'
    response = a.client.post(path, json={'quiet': True, 'provenance': 'synthetic'}, headers=AUTH)
    assert response.status_code == 200, response.text
    a.engine.dispose()
    response = a.client.post(path, json=patch, headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.json()['purpose'] == expected
    upload = initiate(a); complete(a, upload)
    assert admission(a, upload).json()['provenance'] == expected  # no KV flags at this boundary
    assert a.client.post(path, json={'quiet': False, 'provenance': None}, headers=AUTH).json()['purpose'] is None
    assert admission(a, upload).json()['provenance'] == expected
    v2 = initiate(a, upload['asset_id']); complete(a, v2)
    assert admission(a, v2).json()['provenance'] == 'natural'


@pytest.mark.parametrize('body', [{}, {'quiet': None}, {'quiet': 'true'}, {'purpose': None, 'quiet': False}])
def test_invalid_or_ambiguous_purpose_patch_cannot_clear_mode(timing_pg, body):
    a = timing_pg; assert purpose(a, 'synthetic').status_code == 200
    response = a.client.post('/internal/review/timing-purpose/share', json=body, headers=AUTH)
    assert response.status_code == 422
    upload = natural(a)
    assert admission(a, upload).json()['provenance'] == 'synthetic'


@pytest.mark.parametrize('test_purpose', ['operator-test', 'synthetic'])
def test_confirmed_test_mode_cannot_be_cleared_for_same_physical_version(timing_pg, test_purpose):
    a = timing_pg; upload = natural(a)
    first = admission(a, upload); assert first.status_code == 200, first.text
    assert first.json()['provenance'] == 'natural'
    assert status(a, upload).json()['eligible'] == [0]
    assert purpose(a, test_purpose).status_code == 200
    assert admission(a, upload).json()['provenance'] == test_purpose  # stale quiet=false
    assert purpose(a, None).status_code == 200
    a.engine.dispose()  # subsequent sessions use new connections, not process cache
    assert admission(a, upload).json()['provenance'] == test_purpose
    assert status(a, upload).json()['eligible'] == []
    # Frozen origin independently remains natural, only the negative mark changed.
    from apps.api.models import RequestUpload
    with a.Session() as db: assert db.query(RequestUpload).one().timing_provenance['provenance'] == 'natural'


@pytest.mark.parametrize('reason', ['operator-test', 'synthetic', 'unknown', 'unclassified'])
def test_observed_prior_non_natural_is_monotone_and_v2_is_independent(timing_pg, reason):
    a = timing_pg; v1 = natural(a)
    first = admission(a, v1, reason); assert first.status_code == 200, first.text
    assert first.json()['provenance'] == reason
    assert admission(a, v1).json()['provenance'] == reason
    assert admission(a, v1, 'synthetic').json()['provenance'] == reason  # first mark immutable
    v2 = initiate(a, v1['asset_id']); complete(a, v2)
    assert admission(a, v2).json()['provenance'] == 'natural'


def test_active_mode_applies_to_new_submissions_before_kv_observes_flags(timing_pg):
    a = timing_pg; assert intent(a).status_code == 200
    response = purpose(a, 'synthetic'); assert response.status_code == 200, response.text
    v1 = initiate(a); complete(a, v1)
    assert admission(a, v1).json()['provenance'] == 'synthetic'
    assert purpose(a, None).status_code == 200
    assert admission(a, v1).json()['provenance'] == 'synthetic'
    v2 = initiate(a, v1['asset_id']); complete(a, v2)
    assert admission(a, v2).json()['provenance'] == 'natural'


def test_exclusion_is_not_clearable_or_transferable_to_another_physical_asset(timing_pg):
    from apps.api.models import AssetVersion
    a = timing_pg; upload = natural(a); assert admission(a, upload, 'operator-test').status_code == 200
    with a.Session() as db:
        row = db.get(AssetVersion, uuid.UUID(upload['version_id'])); before = row.timing_exclusion
        row.timing_exclusion = None
        with pytest.raises(DBAPIError): db.commit()
        db.rollback(); row = db.get(AssetVersion, row.id); row.timing_exclusion = {**before, 'provenance': 'natural'}
        with pytest.raises(DBAPIError): db.commit()
        db.rollback(); row = db.get(AssetVersion, row.id); row.asset_id = uuid.uuid4()
        with pytest.raises(DBAPIError): db.commit()
        db.rollback()
        assert db.get(AssetVersion, row.id).timing_exclusion == before


@pytest.mark.parametrize('first', ['purpose', 'admission'])
def test_real_transactions_serialize_admission_and_test_switch_both_orders(timing_pg, first):
    from apps.api.services.review_timing import admit_timing, set_timing_purpose
    a = timing_pg; upload = natural(a)
    with a.Session() as holding, ThreadPoolExecutor(max_workers=1) as pool:
        if first == 'purpose':
            set_timing_purpose(holding, 'share', 'operator-test')
            future = pool.submit(lambda: admission(a, upload))
        else:
            result = admit_timing(holding, a.req.id, a.project.id, 'share', uuid.UUID(upload['asset_id']), uuid.UUID(upload['version_id']))
            assert result['provenance'] == 'natural'
            future = pool.submit(lambda: purpose(a, 'operator-test'))
        try: assert_lock_wait(a); holding.commit()
        finally: holding.rollback()
        assert future.result(5).status_code == 200
    assert admission(a, upload).json()['provenance'] == 'operator-test'
    assert status(a, upload).json()['eligible'] == []  # earlier admitted natural history no longer eligible


def test_rollback_never_confirms_mode_or_exclusion(timing_pg):
    from apps.api.services.review_timing import set_timing_purpose
    from apps.api.models import UploadRequest, AssetVersion
    a = timing_pg; upload = natural(a)
    with a.Session() as db:
        set_timing_purpose(db, 'share', 'synthetic'); db.flush(); db.rollback()
        assert db.get(UploadRequest, a.req.id).timing_run_purpose is None
        assert db.get(AssetVersion, uuid.UUID(upload['version_id'])).timing_exclusion is None
    assert admission(a, upload).json()['provenance'] == 'natural'


@pytest.mark.parametrize('field', ['project_id', 'asset_id', 'version_id', 'share_token'])
def test_wrong_scope_cannot_admit_or_mark_an_unrelated_version(timing_pg, field):
    a = timing_pg; upload = natural(a)
    wrong = 'other' if field == 'share_token' else str(uuid.uuid4())
    assert admission(a, upload, 'synthetic', **{field: wrong}).status_code == 404
    assert admission(a, upload).json()['provenance'] == 'natural'


def test_duplicate_other_order_cannot_launder_a_tested_physical_version(timing_pg):
    from apps.api.models import UploadRequest, RequestUpload
    a = timing_pg; upload = natural(a); assert admission(a, upload, 'operator-test').status_code == 200
    with a.Session() as db:
        other = UploadRequest(token='other-upload', review_share_token='share', title='LOCAL other', project_id=a.project.id, folder_id=a.folder.id, created_by=a.owner.id)
        db.add(other); db.flush(); old = db.query(RequestUpload).one()
        db.add(RequestUpload(request_id=other.id, asset_id=old.asset_id, version_number=1, submitted_at=old.submitted_at, timing_provenance={**old.timing_provenance, 'upload_request_id': str(other.id)}, uploader_name='LOCAL', uploader_email='local@example.test')); db.commit()
    assert admission(a, upload).status_code == 409
    assert status(a, upload).json()['eligible'] == []


def test_api_never_exposes_negative_authority_or_grants_read_only_writes(timing_pg):
    a = timing_pg; upload = natural(a)
    body = dict(project_id=str(a.project.id), share_token='share', asset_id=upload['asset_id'], version_id=upload['version_id'], exclusion='synthetic')
    for headers in [{}, {'x-api-key': 'LOCAL-read-key'}, {'authorization': 'Bearer normal-owner'}]:
        assert a.client.post(f'/internal/review/timing-admission/{a.req.id}', json=body, headers=headers).status_code == 401
        assert a.client.post('/internal/review/timing-purpose/share', json={'purpose': 'operator-test'}, headers=headers).status_code == 401
        assert a.client.post('/internal/review/timing-status', json={'versions': []}, headers=headers).status_code == 401
    assert a.client.post('/internal/review/timing-purpose/share', json={'purpose': 'natural'}, headers=AUTH).status_code == 422
    assert a.client.post(f'/internal/review/timing-admission/{a.req.id}', json={**body, 'excluded_at': '2000-01-01'}, headers=AUTH).status_code == 422
    assert admission(a, upload, 'synthetic').status_code == 200
    assert context(a, upload)['timing_context']['submission_provenance']['schema_version'] == 'autoreview.submission-provenance.v2'
    public = a.client.get('/r/upload'); assert public.status_code == 200
    assert not any(s in public.text for s in ('timing_exclusion', 'timing_run_purpose', 'excluded_at'))


def test_migration_reupgrade_does_not_restore_natural_eligibility(timing_pg):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    a = timing_pg; upload = natural(a); assert admission(a, upload, 'operator-test').status_code == 200
    path = Path(__file__).parents[1] / 'alembic/versions/f1d8a10b2026_timing_test_exclusion.py'
    spec = importlib.util.spec_from_file_location('exclusion_migration', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with a.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade(); module.upgrade()
    # Loss of exclusion authority during downgrade cannot promote existing committed versions.
    assert admission(a, upload).json()['provenance'] == 'unknown'
    assert status(a, upload).json()['eligible'] == []


@pytest.mark.skipif(not __import__('os').getenv('TIMING_WORKER_PATH'), reason='opt-in actual local Node Worker checkout')
def test_actual_node_resolver_http_authority_survives_api_restart_and_stale_flags(timing_pg, tmp_path):
    import json
    import os
    import socket
    import subprocess
    import threading
    import time
    from pathlib import Path
    import uvicorn
    from fastapi import FastAPI
    from apps.api.database import get_db
    from apps.api.routers.review_timing import router
    a = timing_pg; v1 = natural(a)
    worker = Path(os.environ['TIMING_WORKER_PATH'])
    assert worker.is_absolute() and (worker / 'src/timing-authority.ts').is_file()
    node = os.environ.get('TIMING_NODE_PATH', '/Users/alansimon/.nvm/versions/node/v22.22.3/bin/node')
    script = tmp_path / 'durable-exclusion.ts'
    script.write_text('''import {strict as assert} from 'node:assert';
import {resolveTimingIntent} from "''' + str(worker / 'src/timing-intent.ts') + '''";
import {postTimingAdmission,setTimingPurpose} from "''' + str(worker / 'src/timing-authority.ts') + '''";
const [base,quiet,want]=process.argv.slice(2);
const data=await (await fetch(base+'/local-context')).json() as any;
const context=data.timing_context,p=context.submission_provenance;
const env={FREEFRAME_BASE:base,FREEFRAME_BRIDGE_SECRET:'LOCAL-bridge'};
const stale={get:async()=>null,list:async()=>({keys:[],list_complete:true})};
const input={token:'share',assetId:p.asset_id,versionId:p.version_id,context,admit:body=>postTimingAdmission(env,body)};
let previous;
if(quiet==='partial'){
 assert.deepEqual(await setTimingPurpose(env,'share',{quiet:true,provenance:'synthetic'}),{quiet:true,provenance:'synthetic'});
 assert.deepEqual(await setTimingPurpose(env,'share',{quiet:false}),{quiet:false,provenance:'synthetic'});
}
const result=await resolveTimingIntent(stale,{...input,quiet:quiet==='true',previous});
assert.equal(result.authoritative,true);assert.equal(result.provenance,want);
if(quiet==='partial')assert.deepEqual(await setTimingPurpose(env,'share',{quiet:false,provenance:null}),{quiet:false,provenance:null});
console.log(JSON.stringify({sameVersion:p.version_number===1,quiet,provenance:result.provenance,authority:'actual-local-PostgreSQL',providers:0}));
''')
    for upload, quiet, expected in [(v1, 'true', 'operator-test'), (v1, 'false', 'operator-test'),
        (None, 'false', 'natural'), (None, 'partial', 'operator-test'), (None, 'false', 'natural')]:
        if upload is None:
            upload = initiate(a, v1['asset_id']); complete(a, upload)
        app = FastAPI(); app.include_router(router)
        def database():
            with a.Session() as db: yield db
        app.dependency_overrides[get_db] = database
        @app.get('/local-context')
        def local_context(): return context(a, upload)
        sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
        thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True); thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and time.monotonic() < deadline: time.sleep(.01)
            assert server.started
            result = subprocess.run([node, str(worker / 'node_modules/vite-node/vite-node.mjs'), str(script), f'http://127.0.0.1:{port}', quiet, expected], cwd=worker, capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, result.stdout + result.stderr
            print(result.stdout.strip())
        finally:
            server.should_exit = True; thread.join(5); sock.close()
            assert not thread.is_alive()


@pytest.mark.parametrize('first', ['purpose', 'submission'])
def test_test_mode_and_first_submission_serialize_both_lock_orders(timing_pg, first):
    from apps.api.models import RequestUpload, AssetVersion
    from apps.api.routers.requests import locked_request
    from apps.api.services.review_timing import freeze_submission_timing, set_timing_purpose
    a = timing_pg; assert intent(a).status_code == 200; upload = initiate(a)
    with a.Session() as holding, ThreadPoolExecutor(max_workers=1) as pool:
        req = locked_request(holding, a.req.id)
        if first == 'purpose':
            set_timing_purpose(holding, 'share', 'synthetic')
            future = pool.submit(lambda: complete(a, upload))
        else:
            version = holding.get(AssetVersion, uuid.UUID(upload['version_id']))
            record = holding.query(RequestUpload).one()
            freeze_submission_timing(holding, req, record, version); holding.flush()
            future = pool.submit(lambda: purpose(a, 'synthetic'))
        try: assert_lock_wait(a); holding.commit()
        finally: holding.rollback()
        result = future.result(5)
        if first == 'submission': assert result.status_code == 200
    assert purpose(a, None).status_code == 200
    assert admission(a, upload).json()['provenance'] == 'synthetic'


def test_another_request_requires_its_own_attestation_and_negative_does_not_bleed(timing_pg):
    from apps.api.models import UploadRequest, RequestUpload, Asset, AssetVersion
    from apps.api.models.asset import AssetType
    from apps.api.services.review_timing import attest_request_timing, freeze_submission_timing
    from apps.api.routers.requests import locked_request
    a = timing_pg; tested = natural(a); assert admission(a, tested, 'operator-test').status_code == 200
    with a.Session() as db:
        req = UploadRequest(token='other-upload', review_share_token='share', title='LOCAL other', project_id=a.project.id, folder_id=a.folder.id, created_by=a.owner.id)
        asset = Asset(project_id=a.project.id, folder_id=a.folder.id, name='LOCAL other', asset_type=AssetType.video, created_by=a.owner.id)
        db.add_all([req, asset]); db.commit(); request_id, asset_id = req.id, asset.id
    b = SimpleNamespace(**{**vars(a), 'req': req})
    for number, expected in [(1, 'unclassified'), (2, 'natural')]:
        with a.Session() as db:
            if number == 2:
                attest_request_timing(db, request_id, a.project.id, 'share', apply=True); db.commit()
            req = locked_request(db, request_id)
            version = AssetVersion(asset_id=asset_id, version_number=number, created_by=a.owner.id)
            record = RequestUpload(request_id=request_id, asset_id=asset_id, version_number=number, uploader_name='LOCAL', uploader_email='local@example.test')
            db.add_all([version, record]); db.flush()
            freeze_submission_timing(db, req, record, version); db.commit()
            upload = {'asset_id': str(asset_id), 'version_id': str(version.id)}
        assert admission(b, upload).json()['provenance'] == expected
    assert admission(a, tested).json()['provenance'] == 'operator-test'
