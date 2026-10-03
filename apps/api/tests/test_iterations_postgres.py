"""Opt-in durable workflow check against an isolated PostgreSQL schema.

Run with ITERATIONS_TEST_DATABASE_URL pointing to a disposable local database.
Remote review/render/storage calls are mocked; actual ORM writes and leases are not.
"""
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(not os.getenv('ITERATIONS_TEST_DATABASE_URL'), reason='opt-in local PostgreSQL check')


def test_durable_delivery_lease_recovery_and_replacement(monkeypatch):
    from apps.api.database import Base
    from apps.api.models import User, Project, Folder, UploadRequest, Asset, AssetVersion, MediaFile
    from apps.api.models.asset import AssetType, ProcessingStatus, FileType
    from apps.api.services import iteration_runner as runner
    from apps.api.services.iteration_requests import bind_upload, locked_request
    from apps.api.services.iteration_flow import current_recipes
    from apps.api.tests.test_iterations import manifest

    url=os.environ['ITERATIONS_TEST_DATABASE_URL']
    admin=create_engine(url)
    schema='iterations_test_'+uuid.uuid4().hex
    with admin.begin() as conn: conn.execute(text(f'CREATE SCHEMA {schema}'))
    engine=create_engine(url,connect_args={'options':f'-csearch_path={schema}'})
    Session=sessionmaker(bind=engine)
    try:
        Base.metadata.create_all(engine)
        with Session() as db:
            user=User(email='owner@example.test',name='Owner'); db.add(user);db.flush()
            project=Project(name='Test brand',created_by=user.id);db.add(project);db.flush()
            folder=Folder(name='Request',project_id=project.id,created_by=user.id);db.add(folder);db.flush()
            req=UploadRequest(token='request-test',review_share_token='review-test',project_id=project.id,
                folder_id=folder.id,created_by=user.id,title='Iterations',receive_iterations=True,
                iteration_manifest=manifest(),iteration_owner_id=user.id,iteration_state={"submitted":True},iteration_brief='Test briefing')
            db.add(req);db.flush()
            for slot in manifest()['slots']:
                asset=Asset(project_id=project.id,folder_id=folder.id,name=slot['label'],asset_type=AssetType.video,created_by=user.id)
                db.add(asset);db.flush()
                version=AssetVersion(asset_id=asset.id,version_number=1,created_by=user.id,processing_status=ProcessingStatus.ready)
                db.add(version);db.flush()
                db.add(MediaFile(version_id=version.id,file_type=FileType.video,original_filename='part.mp4',mime_type='video/mp4',file_size_bytes=100,s3_key_raw='part.mp4'))
                bind_upload(req,slot,asset,version)
            request_id=req.id;db.commit()

        # A database lease admits one of two simultaneous workers, survives a session restart,
        # and only becomes claimable after expiry.
        def claim():
            with Session() as db: return runner.claim(db,request_id)
        with ThreadPoolExecutor(max_workers=2) as pool: claimed=list(pool.map(lambda _:claim(),range(2)))
        assert sum(t is not None for t in claimed)==1
        assert claim() is None
        with Session() as db:
            req=db.get(UploadRequest,request_id);req.iteration_lease_until=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
        assert claim() is not None
        with Session() as db:
            req=db.get(UploadRequest,request_id);req.iteration_lease_until=None;db.commit()

        # Simulate a replacement while an old review is in flight in another transaction.
        def replace_during_review(db,req,action):
            with Session() as other:
                fresh=locked_request(other,request_id);state=deepcopy(fresh.iteration_state)
                source=state['slots'][action['slot_id']]
                version=AssetVersion(asset_id=uuid.UUID(source['asset_id']),version_number=2,created_by=fresh.created_by,processing_status=ProcessingStatus.ready)
                other.add(version);other.flush()
                source.update(version_id=str(version.id),version_number=2,status='ready')
                fresh.iteration_state=state;other.commit()
            return {'status':'clear','findings':[]}
        monkeypatch.setattr(runner,'perform',replace_during_review)
        with Session() as db: assert runner.run_step(db,request_id)
        with Session() as db:
            source=db.get(UploadRequest,request_id).iteration_state['slots']['opening-a']
            assert source['version_number']==2 and source['status']=='ready'

        # Persist every transition using fresh sessions, including derived Asset/MediaFile/ShareLink.
        monkeypatch.setattr('apps.api.routers.requests._trigger_processing',lambda *args:None)
        def provider(db,req,action):
            if action['kind']=='review_part': return {'status':'clear','findings':[]}
            if action['kind']=='render': return {'status':'rendering','job_id':action['key'],'next_attempt_at':0}
            if action['kind']=='poll_render': return {'status':'reviewing','s3_key':action['key']+'.mp4','size_bytes':100,'import_output':True}
            return {'status':'delivered','findings':[]}
        monkeypatch.setattr(runner,'perform',provider)
        for _ in range(10):
            with Session() as db:
                if not runner.run_step(db,request_id): break
        with Session() as db:
            req=db.get(UploadRequest,request_id)
            outputs=[req.iteration_state['outputs'][key] for _,key in current_recipes(str(req.id),req.iteration_manifest,req.iteration_state,req.iteration_ratio)]
            assert len(outputs)==2 and all(o['status']=='delivered' for o in outputs)
            for out in outputs:
                asset=db.get(Asset,uuid.UUID(out['asset_id']))
                assert asset.iteration_pending is False and asset.folder_id==req.folder_id
                assert db.get(AssetVersion,uuid.UUID(out['version_id'])) is not None
            assert req.iteration_lease_token is None
    finally:
        engine.dispose()
        with admin.begin() as conn: conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def test_simple_handin_seal_owner_scope_and_private_library_boundaries(monkeypatch):
    from fastapi import BackgroundTasks,HTTPException
    from unittest.mock import MagicMock
    from apps.api.database import Base
    from apps.api.models import User,Project,ProjectMember,Asset,AssetVersion,RequestUpload
    from apps.api.models.project import ProjectRole
    from apps.api.models.asset import ProcessingStatus
    from apps.api.routers import requests as rq,iterations as routes
    from apps.api.services.iteration_requests import snapshot,seal,stored_upload
    from apps.api.services.iteration_runner import identity
    from apps.api.services.permissions import validate_asset_in_share
    from apps.api.models.share import ShareLink
    admin=create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL']);schema='handin_'+uuid.uuid4().hex
    with admin.begin() as conn:conn.execute(text(f'CREATE SCHEMA {schema}'))
    engine=create_engine(os.environ['ITERATIONS_TEST_DATABASE_URL'],connect_args={'options':f'-csearch_path={schema}'})
    Session=sessionmaker(bind=engine)
    monkeypatch.setattr(routes,'require_connected',lambda:None)
    monkeypatch.setattr(rq.review_bridge,'register_request',lambda *a,**kw:{'ok':True})
    monkeypatch.setattr(rq,'upload_guard_error',lambda *a:None)
    monkeypatch.setattr(rq,'create_multipart_upload',lambda *a:'multipart')
    monkeypatch.setattr(rq,'complete_multipart_upload',lambda *a:None)
    monkeypatch.setattr(rq.s3_service,'get_s3_client',lambda:MagicMock(head_object=lambda **k:{'ContentLength':100}))
    try:
        Base.metadata.create_all(engine)
        with Session() as db:
            owner=User(email='owner@example.test',name='Owner',is_staff=False)
            editor=User(email='editor@example.com',name='Editor',is_staff=True)
            stranger=User(email='stranger@example.test',name='Other',is_staff=False)
            db.add_all([owner,editor,stranger]);db.flush()
            project=Project(name='Brand',created_by=owner.id);db.add(project);db.flush()
            db.add_all([ProjectMember(project_id=project.id,user_id=owner.id,role=ProjectRole.owner),
                ProjectMember(project_id=project.id,user_id=editor.id,role=ProjectRole.editor)])
            db.commit()
            out=rq.create_request(rq.RequestCreate(project_id=project.id,title='Parts',receive_iterations=True),db,editor)
            req=rq._live_request(db,out['token'])
            assert identity(req)['owner_id']==f'freeframe:{owner.id}' and req.created_by==editor.id
            routes.declare(req.token,routes.Parts(parts=[routes.Part(id='hook',role='hook',label='Hook'),routes.Part(id='body',role='body',label='Body')]),db)
            monkeypatch.setattr(rq,'abort_multipart_upload',lambda *a:None)
            req.iteration_state={**req.iteration_state,'structured':True};db.commit()
            canceled=rq.guest_initiate(req.token,rq.GuestInitiate(slot_id='hook',original_filename='aborted.mp4',mime_type='video/mp4',file_size_bytes=100),db)
            newer=rq.guest_initiate(req.token,rq.GuestInitiate(slot_id='hook',asset_id=uuid.UUID(canceled['asset_id']),
                original_filename='newer.mp4',mime_type='video/mp4',file_size_bytes=100),db)
            rq.guest_abort(req.token,rq.GuestPart(s3_key=canceled['s3_key'],upload_id='multipart',part_number=1),db)
            assert req.iteration_state['slots']['hook']['version_id']==newer['version_id']
            assert db.get(Asset,uuid.UUID(newer['asset_id'])).deleted_at is None
            rq.guest_abort(req.token,rq.GuestPart(s3_key=newer['s3_key'],upload_id='multipart',part_number=1),db)
            assert 'hook' not in req.iteration_state['slots']
            assert db.get(Asset,uuid.UUID(canceled['asset_id'])).deleted_at is not None
            assert db.get(AssetVersion,uuid.UUID(canceled['version_id'])).deleted_at is not None
            assert any(slot['id']=='hook' for slot in req.iteration_manifest['slots'])
            uploads=[]
            for slot in ('hook','body'):
                result=rq.guest_initiate(req.token,rq.GuestInitiate(slot_id=slot,original_filename=slot+'.mp4',mime_type='video/mp4',file_size_bytes=100),db)
                uploads.append(result)
            first=uploads[0]
            rq.guest_complete(req.token,rq.GuestComplete(s3_key=first['s3_key'],upload_id='multipart',parts=[{'PartNumber':1,'ETag':'etag'}],name='Editor',email='editor@example.com'),BackgroundTasks(),db)
            with pytest.raises(HTTPException):seal(req)
            assert not snapshot(req)['can_leave']
            second=uploads[1]
            rq.guest_complete(req.token,rq.GuestComplete(s3_key=second['s3_key'],upload_id='multipart',parts=[{'PartNumber':1,'ETag':'etag'}],name='Editor',email='editor@example.com'),BackgroundTasks(),db)
            seal(req);db.commit()
            assert snapshot(req)['can_leave'] and not snapshot(req)['editor_done']
            with pytest.raises(HTTPException):routes.declare(req.token,routes.Parts(parts=[routes.Part(id='late',role='hook',label='Late')]),db)
            with pytest.raises(HTTPException):routes.owner_parts(project.id,db,stranger)
            with pytest.raises(HTTPException):routes.owner_parts(project.id,db,editor)
            assert routes.project_scope(project.id,db,owner)['owner_id']==f'freeframe:{owner.id}'
            source=db.get(Asset,uuid.UUID(first['asset_id']))
            link=ShareLink(project_id=project.id,token='public',created_by=owner.id)
            with pytest.raises(HTTPException):validate_asset_in_share(db,link,source)
            # A revision is an explicit replacement; it invalidates safe-to-close until stored again.
            revised=rq.guest_initiate(req.token,rq.GuestInitiate(slot_id='hook',asset_id=source.id,
                original_filename='hook-v2.mp4',mime_type='video/mp4',file_size_bytes=100),db)
            assert revised['version_number']==2 and not snapshot(req)['can_leave']
    finally:
        engine.dispose()
        with admin.begin() as conn:conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()
