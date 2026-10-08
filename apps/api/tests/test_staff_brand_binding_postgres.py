"""Real Postgres + signed JWT + TCP HTTP; only the external Trello bridge is a local server."""
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(not os.getenv('ITERATIONS_TEST_DATABASE_URL'), reason='opt-in local PostgreSQL check')
CARD='0123456789abcdef01234567'
BOARD='1234567890abcdef12345678'
OTHER_CARD='1123456789abcdef01234567'
OTHER_BOARD='2234567890abcdef12345678'


@pytest.fixture
def brand_http(monkeypatch):
    from apps.api.config import settings
    from apps.api.database import Base, get_db
    from apps.api.models import User, Project, Folder
    from apps.api.models.user import UserStatus
    from apps.api.models.project import ProjectMember, ProjectRole
    from apps.api.routers import projects, requests, checklists, folders, iterations
    from apps.api.services.auth_service import create_access_token

    admin=create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'])
    schema='staff_brand_'+uuid.uuid4().hex
    with admin.begin() as c: c.execute(text(f'CREATE SCHEMA {schema}'))
    engine=create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'], connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine, expire_on_commit=False)
    cards={CARD:{'card_id':CARD,'short_link':'AbCd1234','board_id':BOARD,'brand_slug':'forward-health-gmbh'},
           'AbCd1234':{'card_id':CARD,'short_link':'AbCd1234','board_id':BOARD,'brand_slug':'forward-health-gmbh'},
           OTHER_CARD:{'card_id':OTHER_CARD,'short_link':'EfGh5678','board_id':OTHER_BOARD,'brand_slug':'audibene-gmbh'}}
    class Bridge(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path in ('/api/v1/checklists/card','/api/gate/card')
            assert self.headers['authorization']=='Bearer local-bridge'
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            gate=cards.pop('_gate',None)
            if gate:
                gate['entered'].set()
                assert gate['release'].wait(8)
            card=cards.get(body['url'].rstrip('/').split('/')[-1])
            self.send_response(200 if card else 404);self.send_header('content-type','application/json');self.end_headers()
            self.wfile.write(json.dumps(({'name':'Exact replay'} if self.path=='/api/gate/card' else card) or {'error':'card-unavailable'}).encode())
        def log_message(self,*args): pass
    bridge=ThreadingHTTPServer(('127.0.0.1',0),Bridge)
    threading.Thread(target=bridge.serve_forever,daemon=True).start()
    monkeypatch.setattr(settings,'review_bridge_url',f'http://127.0.0.1:{bridge.server_port}')
    monkeypatch.setattr(settings,'review_bridge_secret','local-bridge')
    monkeypatch.setattr(settings,'instance_wide_project_access',False)
    monkeypatch.setattr(settings,'frontend_url','https://feedback.example.test')
    monkeypatch.setattr(settings,'service_api_key','read-only-test-key')
    monkeypatch.setattr(settings,'service_api_key_email','owner@example.test')
    monkeypatch.setattr(settings,'iterations_enabled',True)
    monkeypatch.setattr(settings,'mixer_iterations_url','http://local-unused.invalid')
    monkeypatch.setattr(settings,'mixer_iterations_secret','local-unused')
    monkeypatch.setattr(requests,'dispatch_binding',lambda _:None)  # External Celery dispatch only.
    monkeypatch.setattr('apps.api.services.checklists.dispatch_binding',lambda _:None)
    with Session() as db:
        users={kind:User(email=f'{kind}@example.test',name=kind,is_staff=kind!='customer',status=UserStatus.active)
               for kind in ('owner','member','customer','outsider')}
        db.add_all(users.values());db.flush()
        project=Project(id=uuid.UUID('8195bc56-37ba-4764-9208-f4567705aef6'),name='Arbitrary workspace label',created_by=users['owner'].id,is_workspace=True)
        other=Project(id=uuid.UUID('33333333-982f-4632-ad0c-57b45daa2b21'),name='Unrelated label',created_by=users['customer'].id,is_workspace=True)
        audibene=Project(id=uuid.UUID('e6dbff73-982f-4632-ad0c-57b45daa2b21'),name='Second arbitrary staff label',created_by=users['owner'].id,is_workspace=True)
        db.add_all([project,other,audibene]);db.flush()
        db.add_all([ProjectMember(project_id=project.id,user_id=users['owner'].id,role=ProjectRole.owner),
                    ProjectMember(project_id=project.id,user_id=users['member'].id,role=ProjectRole.editor),
                    ProjectMember(project_id=other.id,user_id=users['owner'].id,role=ProjectRole.owner),
                    ProjectMember(project_id=audibene.id,user_id=users['owner'].id,role=ProjectRole.owner)])
        folder=Folder(project_id=project.id,name='Existing card',description=f'https://trello.com/c/{CARD}',created_by=users['owner'].id)
        db.add(folder);db.commit()
        ids={'project':project.id,'other':other.id,'audibene':audibene.id,'folder':folder.id,**{k:u.id for k,u in users.items()}}
    app=FastAPI();app.include_router(projects.router);app.include_router(requests.router);app.include_router(checklists.router);app.include_router(folders.router);app.include_router(iterations.router)
    def database(request: Request):
        with Session() as db:
            if request.headers.get('x-test-preload'):
                # Preserve a real earlier identity-map load while another HTTP request commits.
                db.info['preloaded_project']=db.get(Project,ids['project'])
                gate=cards['_preload_gate'];gate['entered'].set()
                assert gate['release'].wait(8)
            yield db
    app.dependency_overrides[get_db]=database
    # No auth/role overrides: real middleware resolves signed JWTs against the actual users.
    import socket
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen()
    port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',lifespan='off'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    for _ in range(500):
        if server.started: break
        time.sleep(.01)
    assert server.started
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=15) as client:
        headers={k:{'Authorization':'Bearer '+create_access_token(str(u))} for k,u in ids.items() if k in users}
        yield client,Session,ids,headers,cards
    server.should_exit=True;thread.join(5);bridge.shutdown();bridge.server_close();engine.dispose()
    with admin.begin() as c:c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    admin.dispose()


def bind(fixture, *, actor='owner', apply=False, project='project', **extra):
    client,_,ids,headers,_=fixture
    if apply:
        extra={'expected':{'card_id':CARD,'board_id':BOARD,'brand_slug':'forward-health-gmbh'},**extra}
    return client.post(f'/projects/{ids[project]}/review-brand',headers=headers[actor],
                       json={'trello_url':f'https://trello.com/c/{CARD}','apply':apply,**extra})


def test_owner_dry_run_does_not_write_and_apply_is_idempotent(brand_http):
    from apps.api.models.project import Project
    from apps.api.routers.requests import project_brand
    first=bind(brand_http)
    assert first.status_code==200
    assert first.json()['brand_slug']=='forward-health-gmbh'
    assert first.json()['card_id']==CARD
    assert first.json()['applied'] is False
    _,Session,ids,_,_=brand_http
    with Session() as db: assert db.get(Project,ids['project']).review_brand_binding is None
    applied=bind(brand_http,apply=True,expected={key:first.json()[key] for key in ('card_id','board_id','brand_slug')})
    again=bind(brand_http,apply=True)
    assert applied.status_code==again.status_code==200
    assert applied.json()['binding']==again.json()['binding']
    with Session() as db:
        p=db.get(Project,ids['project']);p.name='A different brand-looking name';db.commit()
        assert project_brand(db,p)=='forward-health-gmbh'
        assert p.review_brand_binding['confirmed_by']==str(ids['owner'])


@pytest.mark.parametrize('actor',['member','customer','outsider'])
def test_non_owner_or_customer_cannot_bind_even_with_the_same_card(brand_http,actor):
    assert bind(brand_http,actor=actor,apply=True).status_code==403


def test_forged_bearer_and_read_only_service_key_cannot_bind(brand_http):
    client,_,ids,_,_=brand_http
    path=f'/projects/{ids["project"]}/review-brand'
    body={'trello_url':f'https://trello.com/c/{CARD}','apply':True}
    assert client.post(path,json=body,headers={'authorization':'Bearer forged'}).status_code==401
    assert client.post(path,json=body,headers={'x-api-key':'read-only-test-key'}).status_code==403


def test_client_cannot_supply_a_foreign_brand_slug(brand_http):
    assert bind(brand_http,apply=True,brand_slug='audibene-gmbh').status_code==422


def test_staff_owner_cannot_bind_a_customer_owned_project(brand_http):
    assert bind(brand_http,project='other',apply=True).status_code==403


@pytest.mark.parametrize('change',['deleted_project','not_workspace','deleted_creator','inactive_owner'])
def test_ineligible_workspace_or_owner_is_denied(brand_http,change):
    from apps.api.models.project import Project
    from apps.api.models.user import User,UserStatus
    _,Session,ids,_,_=brand_http
    with Session() as db:
        if change=='deleted_project':db.get(Project,ids['project']).deleted_at=datetime.now(timezone.utc)
        if change=='not_workspace':db.get(Project,ids['project']).is_workspace=False
        if change=='deleted_creator':db.get(User,ids['owner']).deleted_at=datetime.now(timezone.utc)
        if change=='inactive_owner':db.get(User,ids['owner']).status=UserStatus.deactivated
        db.commit()
    assert bind(brand_http,apply=True).status_code in (401,403,404)


@pytest.mark.parametrize('change',['missing_source','unknown_brand','forged_card','forged_board'])
def test_unattested_or_forged_source_identity_is_denied(brand_http,change):
    *_,cards=brand_http
    if change=='missing_source':cards.clear()
    if change=='unknown_brand':cards[CARD]['brand_slug']=None
    if change=='forged_card':cards[CARD]['card_id']=OTHER_CARD
    if change=='forged_board':cards[CARD]['board_id']='not-a-stable-id'
    assert bind(brand_http,apply=True).status_code in (409,503)


def test_existing_multiple_board_identities_block_binding(brand_http):
    from apps.api.models.folder import Folder
    _,Session,ids,_,_=brand_http
    with Session() as db:
        db.add(Folder(project_id=ids['project'],name='Another board',description=f'https://trello.com/c/{OTHER_CARD}',created_by=ids['owner']));db.commit()
    assert bind(brand_http,apply=True).status_code==409


def test_confirmed_identity_cannot_be_rebound_to_a_different_board(brand_http):
    assert bind(brand_http,apply=True).status_code==200
    client,_,ids,headers,_=brand_http
    response=client.post(f'/projects/{ids["project"]}/review-brand',headers=headers['owner'],
                        json={'trello_url':f'https://trello.com/c/{OTHER_CARD}','apply':True})
    assert response.status_code==409


def test_binding_preserves_frozen_assignment_and_requires_new_request(brand_http):
    from apps.api.models.upload_request import UploadRequest
    from apps.api.models.share import ShareLink,SharePermission
    from apps.api.models.checklist_binding import ChecklistBinding
    from apps.api.services.checklists import snapshot_digest
    client,Session,ids,headers,_=brand_http
    intent={'brand':'arbitrary-workspace-label','brief_text':'Original immutable brief'}
    with Session() as db:
        share=ShareLink(folder_id=ids['folder'],created_by=ids['owner'],token='original-share',permission=SharePermission.comment)
        db.add(share);db.flush()
        req=UploadRequest(project_id=ids['project'],folder_id=ids['folder'],created_by=ids['owner'],token='original-editor',title='Original',brand_slug='arbitrary-workspace-label',review_share_token=share.token,brief_excerpt='Original immutable brief')
        db.add(req);db.flush()
        db.add(ChecklistBinding(project_id=ids['project'],folder_id=ids['folder'],request_id=req.id,created_by=ids['owner'],source_key=f'trello:{CARD}',trello_card_id=CARD,review_share_token=share.token,intent=intent,intent_sha256=snapshot_digest(intent)));db.commit()
    proposal=bind(brand_http)
    assert proposal.status_code==200 and proposal.json()['requires_new_assignment'] is True
    assert bind(brand_http,apply=True).status_code==200
    with Session() as db:
        assert db.query(UploadRequest).one().brand_slug=='arbitrary-workspace-label'
        assert db.query(ChecklistBinding).one().intent==intent
    old=client.get('/internal/review/editor-target/original-editor',headers={'authorization':'Bearer local-bridge'})
    assert old.status_code==200 and old.json()['brand']=='arbitrary-workspace-label'
    assert client.post(f'/folders/{ids["folder"]}/editor-request',headers=headers['owner']).status_code==409
    prepared=client.post('/checklists',headers=headers['owner'],json={'project_id':str(ids['project']),'trello_url':f'https://trello.com/c/{CARD}'})
    assert prepared.status_code==409
    new=client.post('/requests',headers=headers['owner'],json={'project_id':str(ids['project']),'title':'Explicit new assignment','brief_text':'New brief'})
    assert new.status_code==201
    assert new.json()['brand_slug']=='forward-health-gmbh'
    assert new.json()['folder_id']!=str(ids['folder'])


def test_bound_workspace_rejects_foreign_board_in_all_new_handin_paths(brand_http):
    assert bind(brand_http,apply=True).status_code==200
    client,_,ids,headers,_=brand_http
    url=f'https://trello.com/c/{OTHER_CARD}'
    assert client.post('/checklists',headers=headers['owner'],json={'project_id':str(ids['project']),'trello_url':url}).status_code==409
    assert client.post('/requests',headers=headers['owner'],json={'project_id':str(ids['project']),'title':'Wrong board','brief_url':url}).status_code==409
    assert client.post(f'/projects/{ids["project"]}/folders',headers=headers['owner'],json={'name':'Wrong board','description':url}).status_code==409


def test_customer_namespace_ignores_an_injected_staff_binding(brand_http):
    from apps.api.models.project import Project
    client,Session,ids,headers,_=brand_http
    with Session() as db:
        db.get(Project,ids['other']).review_brand_binding={'brand_slug':'forward-health-gmbh','board_id':BOARD}
        db.commit()
    response=client.post('/requests',headers=headers['owner'],json={'project_id':str(ids['other']),'title':'Customer namespace'})
    assert response.status_code==201
    assert response.json()['brand_slug']=='cust-33333333982f4632'


def test_concurrent_confirmation_preserves_one_owner_attestation(brand_http):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:bind(brand_http,apply=True),range(2)))
    assert [r.status_code for r in responses]==[200,200]
    assert responses[0].json()['binding']==responses[1].json()['binding']


def test_new_request_waits_for_brand_confirmation_before_freezing_identity(brand_http):
    from concurrent.futures import ThreadPoolExecutor
    client,Session,ids,headers,cards=brand_http
    gate={'entered':threading.Event(),'release':threading.Event()}
    cards['_gate']=gate
    with ThreadPoolExecutor(max_workers=2) as pool:
        binding=pool.submit(lambda:bind(brand_http,apply=True))
        assert gate['entered'].wait(5)
        request=pool.submit(lambda:client.post('/requests',headers=headers['owner'],
            json={'project_id':str(ids['project']),'title':'Concurrent assignment'}))
        try:
            with Session() as db:
                deadline=time.monotonic()+5
                while not db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'")).scalar():
                    db.rollback()  # PostgreSQL caches statistics until the transaction ends.
                    assert time.monotonic()<deadline
                    time.sleep(.02)
            assert not request.done()
        finally:
            gate['release'].set()
        assert binding.result(10).status_code==200
        response=request.result(10)
    assert response.status_code==201
    assert response.json()['brand_slug']=='forward-health-gmbh'


@pytest.mark.parametrize('value',[[], 'invalid', {}, {'brand_slug':None,'board_id':BOARD},
    {'brand_slug':'forward-health-gmbh','board_id':BOARD},
    {'brand_slug':'forward-health-gmbh','board_id':BOARD,'card_id':CARD,'confirmed_by':'not-an-owner','confirmed_at':'yesterday'}])
def test_malformed_persisted_identity_fails_closed(brand_http,value):
    from apps.api.models.project import Project
    client,Session,ids,headers,_=brand_http
    with Session() as db:
        db.get(Project,ids['project']).review_brand_binding=value;db.commit()
    response=client.post('/requests',headers=headers['owner'],json={'project_id':str(ids['project']),'title':'Must fail closed'})
    assert response.status_code==409


@pytest.mark.parametrize('adoption',['new_folder','existing_folder','already_attached'])
def test_old_frozen_binding_cannot_be_adopted_after_brand_confirmation(brand_http,adoption):
    from apps.api.models.checklist_binding import ChecklistBinding
    from apps.api.services.checklists import snapshot_digest
    client,Session,ids,headers,_=brand_http
    intent={'brand':'old-workspace-label','brief_url':f'https://trello.com/c/{CARD}'}
    with Session() as db:
        binding=ChecklistBinding(project_id=ids['project'],created_by=ids['owner'],source_key=f'trello:{CARD}',
            trello_card_id=CARD,intent=intent,intent_sha256=snapshot_digest(intent),
            folder_id=ids['folder'] if adoption=='already_attached' else None)
        db.add(binding);db.commit();binding_id=str(binding.id)
    assert bind(brand_http,apply=True).status_code==200
    body={'name':'Must not adopt','description':f'https://trello.com/c/{CARD}','checklist_binding_id':binding_id}
    if adoption=='existing_folder':body['existing_folder_id']=str(ids['folder'])
    response=client.post(f'/projects/{ids["project"]}/folders',headers=headers['owner'],json=body)
    assert response.status_code==409
    with Session() as db:assert db.get(ChecklistBinding,binding_id).intent==intent


def test_native_handin_refreshes_a_preloaded_project_after_confirmation(brand_http):
    from concurrent.futures import ThreadPoolExecutor
    client,_,ids,headers,cards=brand_http
    gate={'entered':threading.Event(),'release':threading.Event()};cards['_preload_gate']=gate
    with ThreadPoolExecutor(max_workers=1) as pool:
        handin=pool.submit(lambda:client.post('/handins',headers={**headers['owner'],'x-test-preload':'1'},json={
            'project_id':str(ids['project']),'card_url':'https://trello.com/c/AbCd1234','idempotency_key':str(uuid.uuid4())}))
        assert gate['entered'].wait(5)
        try:assert bind(brand_http,apply=True).status_code==200
        finally:gate['release'].set()
        response=handin.result(10)
    assert response.status_code==201,response.text
    assert response.json()['brand_slug']=='forward-health-gmbh'


def test_native_and_request_replay_have_consistent_lock_order(brand_http,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from apps.api.routers import requests
    client,Session,ids,headers,_=brand_http
    key=str(uuid.uuid4())
    body={'project_id':str(ids['project']),'title':'Exact replay','brief_url':'https://trello.com/c/AbCd1234',
          'receive_iterations':True,'idempotency_key':key}
    first=client.post('/requests',headers=headers['owner'],json=body)
    assert first.status_code==201,first.text
    entered=threading.Event();release=threading.Event();original=requests.reserve_binding
    def reservation(*args,**kwargs):
        if not entered.is_set():
            entered.set();assert release.wait(8)
        return original(*args,**kwargs)
    monkeypatch.setattr(requests,'reserve_binding',reservation)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replay=pool.submit(lambda:client.post('/requests',headers=headers['owner'],json=body))
        assert entered.wait(5)
        native=pool.submit(lambda:client.post('/handins',headers=headers['owner'],json={
            'project_id':str(ids['project']),'card_url':body['brief_url'],'idempotency_key':key}))
        try:
            with Session() as db:
                deadline=time.monotonic()+5
                while not db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'")).scalar():
                    db.rollback();assert time.monotonic()<deadline;time.sleep(.02)
        finally:release.set()
        responses=[replay.result(10),native.result(10)]
    assert [r.status_code for r in responses]==[201,201],[r.text for r in responses]
    assert all(r.json()['id']==first.json()['id'] for r in responses)


def test_operator_dry_run_for_both_concrete_staff_workspace_ids(brand_http):
    from apps.api.models.project import Project
    client,Session,ids,headers,_=brand_http
    for project,card,brand in [('project',CARD,'forward-health-gmbh'),('audibene',OTHER_CARD,'audibene-gmbh')]:
        response=client.post(f'/projects/{ids[project]}/review-brand',headers=headers['owner'],
            json={'trello_url':f'https://trello.com/c/{card}','apply':False})
        assert response.status_code==200,response.text
        assert response.json()['brand_slug']==brand and response.json()['applied'] is False
    with Session() as db:
        assert all(db.get(Project,ids[key]).review_brand_binding is None for key in ('project','audibene'))


def test_apply_requires_the_reviewed_identity_tuple(brand_http):
    from apps.api.models.project import Project
    client,Session,ids,headers,_=brand_http
    proposal=bind(brand_http)
    assert proposal.status_code==200
    response=client.post(f'/projects/{ids["project"]}/review-brand',headers=headers['owner'],
        json={'trello_url':f'https://trello.com/c/{CARD}','apply':True})
    assert response.status_code==409
    with Session() as db: assert db.get(Project,ids['project']).review_brand_binding is None


def test_apply_rejects_card_moved_after_the_reviewed_proposal(brand_http):
    from apps.api.models.project import Project
    client,Session,ids,headers,cards=brand_http
    proposal=bind(brand_http)
    assert proposal.status_code==200 and proposal.json()['brand_slug']=='forward-health-gmbh'
    cards[CARD].update(board_id=OTHER_BOARD,brand_slug='audibene-gmbh')
    response=bind(brand_http,apply=True,expected={'card_id':CARD,'board_id':BOARD,'brand_slug':proposal.json()['brand_slug']})
    assert response.status_code==409
    with Session() as db: assert db.get(Project,ids['project']).review_brand_binding is None


@pytest.mark.parametrize('changed',[
    {'card_id':OTHER_CARD}, {'board_id':OTHER_BOARD}, {'brand_slug':'audibene-gmbh'},
])
def test_expected_fields_are_comparisons_not_identity_authority(brand_http,changed):
    from apps.api.models.project import Project
    _,Session,ids,_,_=brand_http
    expected={'card_id':CARD,'board_id':BOARD,'brand_slug':'forward-health-gmbh',**changed}
    assert bind(brand_http,apply=True,expected=expected).status_code==409
    with Session() as db: assert db.get(Project,ids['project']).review_brand_binding is None


@pytest.mark.parametrize('scope',['foreign','unavailable'])
def test_preupload_assignment_check_refuses_unverified_scope_but_completed_work_remains_readable(brand_http,scope):
    from apps.api.models.asset import Asset, AssetVersion, AssetType, ProcessingStatus
    from apps.api.models.upload_request import UploadRequest, RequestUpload
    from apps.api.models.share import ShareLink, SharePermission
    client,Session,ids,headers,cards=brand_http
    assert bind(brand_http,apply=True).status_code==200
    with Session() as db:
        share=ShareLink(folder_id=ids['folder'],created_by=ids['owner'],token='completed-share',
            title='Auto Review',permission=SharePermission.comment)
        db.add(share);db.flush()
        req=UploadRequest(project_id=ids['project'],folder_id=ids['folder'],created_by=ids['owner'],
            token='completed-editor',title='Finished cut',review_share_token=share.token,
            brand_slug='legacy-label' if scope=='foreign' else 'forward-health-gmbh',
            brief_excerpt='Frozen completed brief',completed_at=datetime.now(timezone.utc))
        asset=Asset(project_id=ids['project'],folder_id=ids['folder'],name='Finished cut',
            asset_type=AssetType.video,created_by=ids['owner'])
        db.add_all([req,asset]);db.flush()
        version=AssetVersion(asset_id=asset.id,version_number=1,created_by=ids['owner'],processing_status=ProcessingStatus.ready)
        db.add(version);db.commit();asset_id=str(asset.id);request_id=req.id
    if scope=='unavailable': cards.clear()
    preflight=client.post(f'/folders/{ids["folder"]}/editor-request',headers=headers['owner'])
    assert preflight.status_code==(409 if scope=='foreign' else 503),preflight.text
    readable=client.get('/r/completed-editor')
    assert readable.status_code==200,readable.text
    assert readable.json()['completed_at'] and readable.json()['brief_excerpt']=='Frozen completed brief'
    assert readable.json()['assets']==[{'id':asset_id,'name':'Finished cut'}]
    with Session() as db:
        assert db.query(UploadRequest).count()==1 and db.get(UploadRequest,request_id).completed_at
        assert db.query(AssetVersion).count()==1 and db.query(RequestUpload).count()==0
