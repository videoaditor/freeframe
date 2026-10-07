"""Committed insertion races in an explicitly disposable local PostgreSQL database."""
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark=pytest.mark.skipif(not os.getenv('ITERATIONS_TEST_DATABASE_URL'),reason='opt-in local PostgreSQL check')


@pytest.fixture
def bound_sessions():
    from apps.api.database import Base
    from apps.api import models
    from apps.api.models.user import User
    from apps.api.models.project import Project
    url=os.environ['ITERATIONS_TEST_DATABASE_URL']
    assert 'bound_producer_h2_test' in url, 'requires own disposable database'
    admin=create_engine(url); schema='bound_producer_'+uuid.uuid4().hex
    with admin.begin() as c: c.execute(text(f'CREATE SCHEMA {schema}'))
    engine=create_engine(url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as db:
        user=User(email='synthetic@example.test',name='Synthetic');db.add(user);db.flush()
        project=Project(name='Synthetic',created_by=user.id);db.add(project);db.commit()
        ids=(project.id,user.id)
    try: yield Session,ids
    finally:
        engine.dispose()
        with admin.begin() as c: c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


@pytest.mark.parametrize('first_selected',[False,True])
def test_unique_insert_winner_freezes_selection_across_config_race(bound_sessions,monkeypatch,first_selected):
    from apps.api.services.checklists import reserve_binding,snapshot_digest
    from apps.api.config import settings
    from apps.api.models.checklist_binding import ChecklistBinding
    Session,(project,user)=bound_sessions
    monkeypatch.setattr(settings,'bound_review_project_ids',str(project) if first_selected else '')
    inserted=threading.Event(); release=threading.Event(); second_started=threading.Event()
    def first():
        with Session() as db:
            b=reserve_binding(db,project,user,'request:race',{'brand':'demo'})
            inserted.set();assert release.wait(5);db.commit();return b.id
    def second():
        with Session() as db:
            second_started.set()
            b=reserve_binding(db,project,user,'request:race',{'brand':'demo'})
            db.commit();return b.id
    with ThreadPoolExecutor(max_workers=2) as pool:
        f=pool.submit(first);assert inserted.wait(5)
        monkeypatch.setattr(settings,'bound_review_project_ids','' if first_selected else str(project))
        s=pool.submit(second);assert second_started.wait(5)
        # A separate connection proves the second INSERT is blocked by the unique winner.
        with Session() as db:
            deadline=time.monotonic()+3
            while True:
                waiting=db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'")).scalar()
                if waiting: break
                assert time.monotonic()<deadline, 'competing insertion did not reach a PostgreSQL lock'
                time.sleep(0.02)
            assert not s.done()
        release.set();assert f.result(5)==s.result(5)
    with Session() as db:
        b=db.query(ChecklistBinding).one()
        assert ('review_engine' in b.intent)==first_selected
        assert b.intent_sha256==snapshot_digest(b.intent)
        original=(b.intent.copy(),b.intent_sha256)
        assert reserve_binding(db,project,user,'request:race',{'brand':'demo'}).id==b.id
        assert (b.intent,b.intent_sha256)==original


def test_selected_internal_folder_creates_share_and_authenticated_outbox_without_legacy_webhook(bound_sessions,monkeypatch):
    from unittest.mock import patch
    from apps.api.config import settings
    from apps.api.services.checklists import reserve_binding,snapshot_digest
    from apps.api.routers.folders import create_folder
    from apps.api.schemas.folder import FolderCreate
    from apps.api.tasks.checklist_tasks import _register
    from apps.api.models.user import User
    from apps.api.models.share import ShareLink
    Session,(project,user)=bound_sessions
    monkeypatch.setattr(settings,'bound_review_project_ids',str(project))
    monkeypatch.setattr(settings,'automation_share_webhook_url','')
    with Session() as db:
        owner=db.get(User,user);owner.is_staff=True
        card='0123456789abcdef01234567'
        b=reserve_binding(db,project,user,'trello:'+card,{'brand':'synthetic','brief_url':'https://trello.com/c/'+card},card)
        db.commit();identity=b.id;fullhash=b.intent_sha256
        with patch('apps.api.routers.folders.require_project_role'), patch('apps.api.routers.folders._folder_to_response',return_value={}), patch('apps.api.services.checklists.dispatch_binding') as dispatch, patch('apps.api.routers.folders.automation_share.announce_folder') as announce:
            create_folder(project,FolderCreate(name='Synthetic',description='https://trello.com/c/'+card,checklist_binding_id=identity),db,owner)
        announce.assert_not_called();dispatch.assert_called_once_with(identity)
        db.expire_all();b=db.get(type(b),identity)
        link=db.query(ShareLink).filter_by(token=b.review_share_token).one()
        assert link.folder_id==b.folder_id and link.project_id is None
        assert link.permission.value=='comment' and link.allow_download and link.visibility=='public'
        # Restart after commit with a changed allowlist: outbox selection stays frozen.
    monkeypatch.setattr(settings,'bound_review_project_ids','')
    with Session() as db:
        from apps.api.models.checklist_binding import ChecklistBinding
        b=db.get(ChecklistBinding,identity)
        with patch('apps.api.tasks.checklist_tasks.review_bridge.register_request',return_value={'ok':True}) as send:
            _register(db,b)
        assert send.call_args.kwargs['engine']=='continuity-v1'
        assert send.call_args.kwargs['tenant_id']==str(project)
        assert send.call_args.kwargs['request_id']==str(identity)
        assert send.call_args.kwargs['checklist']['plan_id'] is None
        assert b.registered_at and b.intent_sha256==fullhash==snapshot_digest(b.intent)
