"""Run only against a disposable DB: H1 migration + concurrency/persistence proof.
Usage: DATABASE_URL=<isolated postgres> ... python scripts/verify-h1-postgres.py
"""
import os
import sys
import uuid
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from apps.api.models.checklist_binding import ChecklistBinding
from apps.api.models.user import User
from apps.api.models.project import Project, ProjectType
from apps.api.services.checklists import reserve_binding

root=Path(__file__).resolve().parents[1]
url=os.environ['DATABASE_URL']
if 'freeframe_h1' not in url:
    raise SystemExit('Requires disposable freeframe_h1 database')
engine=create_engine(url)
def migrate(*args):
    subprocess.run([sys.executable,'-m','alembic',*args],cwd=root/'apps/api',check=True)
migrate('upgrade','head')
user_id=uuid.uuid4(); project_id=uuid.uuid4()
with Session(engine) as db:
    db.add(User(id=user_id,email=f'h1-{user_id}@example.invalid',name='H1 fixture',password_hash='test'))
    db.flush()
    db.add(Project(id=project_id,name='Synthetic H1',project_type=ProjectType.team,created_by=user_id))
    db.commit()
intent={'brand':'synthetic','title':'Synthetic card','brief_text':'Keep product visible.','brief_url':'','brief_pdf_base64':''}
def reserve(_):
    with Session(engine) as db:
        row=reserve_binding(db,project_id,user_id,'trello:0123456789abcdef01234567',intent,'0123456789abcdef01234567')
        key=str(row.id); db.commit(); return key
with ThreadPoolExecutor(max_workers=4) as pool:
    ids=list(pool.map(reserve,range(4)))
assert len(set(ids))==1,ids
with Session(engine) as db:
    row=db.get(ChecklistBinding,uuid.UUID(ids[0])); assert row.intent==intent and row.folder_id is None
    row.status='failed';db.rollback()
with Session(engine) as db:
    assert db.get(ChecklistBinding,uuid.UUID(ids[0])).status=='queued'
    try:
        reserve_binding(db,project_id,user_id,'trello:0123456789abcdef01234567',{**intent,'brief_text':'Changed'},'0123456789abcdef01234567')
        raise AssertionError('Conflicting brief accepted')
    except Exception as e:
        assert getattr(e,'status_code',None)==409,e
        db.rollback()
engine.dispose()
engine=create_engine(url)
with Session(engine) as db:
    row=db.get(ChecklistBinding,uuid.UUID(ids[0]));assert row.intent==intent and row.status=='queued'
print('PASS: four concurrent prepares -> one binding; rollback; conflict; reconnect; no folder')
from unittest.mock import patch
from apps.api.routers.requests import RequestCreate, create_request
from apps.api.models.folder import Folder
from apps.api.models.upload_request import UploadRequest
from apps.api.models.project import ProjectMember, ProjectRole
with Session(engine) as db:
    db.add(ProjectMember(project_id=project_id,user_id=user_id,role=ProjectRole.owner));db.commit()
create_key=uuid.uuid4()
def request(_):
    with Session(engine) as db:
        user=db.get(User,user_id)
        return create_request(RequestCreate(project_id=project_id,title='Synthetic request',brief_text='Keep product visible.',idempotency_key=create_key),db,user)
with patch('apps.api.routers.requests.dispatch_binding'):
    with ThreadPoolExecutor(max_workers=4) as pool:
        requests=list(pool.map(request,range(4)))
assert len({r['id'] for r in requests})==1
assert len({r['token'] for r in requests})==1
assert len({r['checklist_binding_id'] for r in requests})==1
with Session(engine) as db:
    assert db.query(Folder).filter(Folder.project_id==project_id).count()==1
    assert db.query(UploadRequest).filter(UploadRequest.project_id==project_id).count()==1
    bound=db.get(ChecklistBinding,uuid.UUID(requests[0]['checklist_binding_id']))
    assert bound.request_id==uuid.UUID(requests[0]['id']) and bound.folder_id==uuid.UUID(requests[0]['folder_id'])
print('PASS: four concurrent customer creates -> one link/folder/request/binding, same committed intent')
# A failure during request construction rolls back the binding and folder in the same transaction.
failed_key=uuid.uuid4()
with patch('apps.api.routers.requests.secrets.token_urlsafe',side_effect=RuntimeError('synthetic rollback')):
    try:
        with Session(engine) as db:
            create_request(RequestCreate(project_id=project_id,title='Rollback',idempotency_key=failed_key),db,db.get(User,user_id))
    except RuntimeError:
        pass
with Session(engine) as db:
    assert db.query(ChecklistBinding).filter(ChecklistBinding.source_key==f'request:{failed_key}').count()==0
    assert db.query(Folder).filter(Folder.project_id==project_id).count()==1
print('PASS: failed request rolls back intent and folder')

# Execute the real task using a real Session; only remote bridge calls are fixtures.
from datetime import datetime, timedelta, timezone
from apps.api.tasks.checklist_tasks import prepare_checklist, resume_checklists
bound_id=uuid.UUID(requests[0]['checklist_binding_id'])
with Session(engine) as db:
    bound=db.get(ChecklistBinding,bound_id)
    bound.snapshot={'briefing':{'text':'Frozen instructions'}}
    bound.context_sha256='a'*64;bound.plan_id='fixture-plan';bound.status='running'
    bound.registered_at=datetime.now(timezone.utc);db.commit()
ready={'status':'ready','plan_id':'fixture-plan','context_sha256':'a'*64,'content_sha256':'b'*64,'requirements':[{'id':'fixture'}]}
with patch('apps.api.tasks.checklist_tasks.SessionLocal',side_effect=lambda:Session(engine)), patch('apps.api.services.checklists.review_bridge.checklist_plan',return_value=ready), patch('apps.api.tasks.checklist_tasks.review_bridge.register_request',return_value=None):
    prepare_checklist.run(str(bound_id))
with Session(engine) as db:
    bound=db.get(ChecklistBinding,bound_id)
    assert bound.status=='ready' and bound.content_sha256=='b'*64 and bound.registered_at is None
    assert bound.registration_attempts==1 and bound.next_registration_at>datetime.now(timezone.utc)
    bound.next_registration_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
with patch('apps.api.tasks.checklist_tasks.SessionLocal',side_effect=lambda:Session(engine)), patch('apps.api.tasks.checklist_tasks.review_bridge.register_request',return_value={'ok':True}) as register:
    prepare_checklist.run(str(bound_id))
    assert register.call_args.kwargs['checklist']['content_sha256']=='b'*64
with Session(engine) as db:
    assert db.get(ChecklistBinding,bound_id).registered_at is not None
print('PASS: ready reference delivery failure stays committed; restart retransmits the final hash')

# Exhausted/retired rows must not occupy the recovery window forever.
with Session(engine) as db:
    for n in range(50):
        db.add(ChecklistBinding(project_id=project_id,created_by=user_id,source_key=f'exhausted:{n}',intent=intent,intent_sha256='c'*64,status='failed',review_share_token=f'exhausted-{n}',registration_attempts=3,registration_error='registration-unavailable'))
    fresh=reserve_binding(db,project_id,user_id,'fresh-recovery',intent)
    fresh_id=fresh.id;db.commit()
with patch('apps.api.tasks.checklist_tasks.SessionLocal',side_effect=lambda:Session(engine)),patch('apps.api.tasks.checklist_tasks.prepare_checklist.delay') as dispatch:
    resume_checklists.run()
    dispatched={call.args[0] for call in dispatch.call_args_list}
    assert str(fresh_id) in dispatched
    with Session(engine) as db:
        exhausted=db.query(ChecklistBinding.id).filter(ChecklistBinding.project_id==project_id,ChecklistBinding.registration_attempts>=3).all()
        assert not dispatched.intersection(str(key) for (key,) in exhausted)
print('PASS: fifty exhausted registration rows do not starve a later committed intent')

migrate('downgrade','e4f5a6b7c8d9')
with engine.connect() as c:
    assert c.execute(text("select to_regclass('public.checklist_bindings')")).scalar() is None
migrate('upgrade','head')
print('PASS: migration upgrade/downgrade/re-upgrade')
