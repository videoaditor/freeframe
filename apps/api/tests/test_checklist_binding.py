"""H1: authorization, immutable snapshots and retryable durable intent."""
import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


def test_hash_matches_worker_fixture():
    from apps.api.services.checklists import canonical_json, snapshot_digest
    f = json.loads((Path(__file__).parent / 'fixtures/checklist-canonical-v1.json').read_text())
    assert canonical_json(f['input']) == f['canonical']
    assert snapshot_digest(f['input']) == f['sha256']


def test_internal_prepare_rejects_customer_before_provider_read():
    from apps.api.routers.checklists import prepare_checklist, ChecklistPrepare
    with patch('apps.api.routers.checklists.review_bridge.checklist_card') as lookup:
        with pytest.raises(HTTPException) as e:
            prepare_checklist(ChecklistPrepare(project_id=uuid.uuid4(), trello_url='https://trello.com/c/AbCd1234'), MagicMock(), SimpleNamespace(is_staff=False))
        assert e.value.status_code == 403
        lookup.assert_not_called()


def test_internal_prepare_rejects_unknown_card_without_folder():
    from apps.api.routers.checklists import prepare_checklist, ChecklistPrepare
    db = MagicMock(); db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=uuid.uuid4())
    with patch('apps.api.routers.checklists.require_project_role'), patch('apps.api.routers.checklists.review_bridge.checklist_card', return_value=None):
        with pytest.raises(HTTPException) as e:
            prepare_checklist(ChecklistPrepare(project_id=uuid.uuid4(), trello_url='https://trello.com/c/AbCd1234'), db, SimpleNamespace(is_staff=True))
        assert e.value.status_code == 503
        db.add.assert_not_called()


def test_foreign_project_cannot_adopt_binding():
    from apps.api.services.checklists import binding_for_folder
    db = MagicMock(); row = SimpleNamespace(project_id=uuid.uuid4(), deleted_at=None)
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = row
    with pytest.raises(HTTPException) as e:
        binding_for_folder(db, uuid.uuid4(), uuid.uuid4(), 'https://trello.com/c/AbCd1234')
    assert e.value.status_code == 404


def test_snapshot_identity_tampering_is_rejected():
    from apps.api.services.checklists import validate_snapshot, snapshot_digest
    row = SimpleNamespace(id=uuid.uuid4(), project_id=uuid.uuid4())
    s = {'schema_version': 'autoreview.plan-request.v1', 'tenant_id': str(uuid.uuid4()), 'request_id': str(row.id)}
    with pytest.raises(ValueError):
        validate_snapshot(row, {'snapshot': s, 'context_sha256': snapshot_digest(s)})


def test_failed_bridge_keeps_snapshot_and_reuses_it_after_restart():
    from apps.api.services.checklists import advance_binding, snapshot_digest
    row = SimpleNamespace(id=uuid.uuid4(), project_id=uuid.uuid4(), snapshot=None, context_sha256=None, plan_id=None, status='queued', attempts=0, error_code=None, next_attempt_at=None,
        intent={'brand':'demo','brief_text':'Show product','brief_url':'','brief_pdf_base64':''}, registered_at=None, request_id=None, folder_id=None, plan=None)
    s = {'schema_version': 'autoreview.plan-request.v1', 'tenant_id': str(row.project_id), 'request_id':str(row.id), 'idempotency_key':f'checklist:{row.project_id}:{row.id}', 'briefing':{'text':'Show product'}}
    db=MagicMock()
    with patch('apps.api.services.checklists.review_bridge.checklist_snapshot', return_value={'snapshot':s,'context_sha256':snapshot_digest(s)}) as read, patch('apps.api.services.checklists.review_bridge.checklist_plan', return_value=None) as plan:
        advance_binding(db, row)
        assert row.snapshot == s
        frozen = json.dumps(plan.call_args.args[0], sort_keys=True)
        advance_binding(db, row)
        assert json.dumps(plan.call_args.args[0], sort_keys=True) == frozen
        assert read.call_count == 1
        assert row.status != 'ready'


def test_public_schema_has_no_snapshot_or_quotes():
    from apps.api.services.checklists import binding_out
    row=SimpleNamespace(id=uuid.uuid4(),status='ready',error_code=None,plan_id='p',content_sha256='a'*64,plan={'requirements':[{'id':'r','text':'Show product','sources':[{'layer':'briefing','reference_id':'b','source_version':'v'}]}],'limitations':[]},attempts=1)
    out=binding_out(row)
    assert 'snapshot' not in out
    assert out['requirements'][0]['sources'][0]['layer']=='briefing'


def test_duplicate_customer_create_returns_existing_link_without_new_folder():
    from apps.api.routers.requests import create_request, RequestCreate
    from apps.api.models.upload_request import UploadRequest
    db=MagicMock(); project=SimpleNamespace(id=uuid.uuid4(),name='Demo')
    req=UploadRequest(id=uuid.uuid4(),token='existing',project_id=project.id,folder_id=uuid.uuid4(),created_by=uuid.uuid4(),title='Demo',review_share_token='share')
    row=SimpleNamespace(id=uuid.uuid4(),request_id=req.id,status='queued',error_code=None,plan_id=None,content_sha256=None,plan=None,attempts=0)
    db.query.return_value.filter.return_value.first.side_effect=[project,req]
    with patch('apps.api.routers.requests.require_project_role'), patch('apps.api.routers.requests.project_brand',return_value='demo'), patch('apps.api.routers.requests.reserve_binding',return_value=row), patch('apps.api.routers.requests.dispatch_binding'):
        result=create_request(RequestCreate(project_id=project.id,title='Demo',idempotency_key=uuid.uuid4()),db,SimpleNamespace(id=uuid.uuid4()))
    assert result['token']=='existing'
    db.add.assert_not_called()


def test_adopting_existing_folder_requires_same_project_and_card():
    from apps.api.routers.folders import create_folder
    from apps.api.schemas.folder import FolderCreate
    project_id=uuid.uuid4(); folder_id=uuid.uuid4()
    binding=SimpleNamespace(id=uuid.uuid4(), project_id=project_id, folder_id=None, review_share_token=None)
    folder=SimpleNamespace(id=folder_id,project_id=uuid.uuid4(),description='https://trello.com/c/abc')
    with patch('apps.api.routers.folders.require_project_role'), patch('apps.api.services.checklists.binding_for_folder',return_value=binding), patch('apps.api.routers.folders._get_folder',return_value=folder):
        with pytest.raises(HTTPException) as e:
            create_folder(project_id,FolderCreate(name='Card',checklist_binding_id=binding.id,existing_folder_id=folder_id,description='https://trello.com/c/abc'),MagicMock(),SimpleNamespace(is_staff=True))
    assert e.value.status_code==404


def _task_row():
    from datetime import datetime, timezone
    return SimpleNamespace(id=uuid.uuid4(),project_id=uuid.uuid4(),request_id=None,folder_id=None,
        review_share_token='synthetic',registered_at=datetime.now(timezone.utc),registration_attempts=0,
        registration_error=None,next_registration_at=None,status='running',attempts=0,plan_id='p1',
        content_sha256=None,plan=None,snapshot={'briefing':{'text':'Frozen'}},context_sha256='a'*64,
        intent={'brand':'demo','title':'Synthetic','brief_text':'Frozen','brief_url':'','brief_pdf_base64':''},
        deleted_at=None,error_code=None,next_attempt_at=None)


def test_ready_registration_failure_remains_durable_across_restart():
    from copy import deepcopy
    from apps.api.tasks.checklist_tasks import prepare_checklist
    from apps.api.models.checklist_binding import ChecklistBinding
    from apps.api.models.project import Project
    row=_task_row(); durable={}
    db=MagicMock()
    def query(model):
        q=MagicMock()
        q.filter.return_value.with_for_update.return_value.first.return_value=row
        q.filter.return_value.first.return_value=SimpleNamespace(id=row.project_id) if model is Project else row
        return q
    db.query.side_effect=query
    db.commit.side_effect=lambda: durable.update(deepcopy(vars(row)))
    ready={'plan_id':'p1','context_sha256':row.context_sha256,'status':'ready','content_sha256':'b'*64,'requirements':[{'id':'r'}]}
    with patch('apps.api.tasks.checklist_tasks.SessionLocal',return_value=db), patch('apps.api.services.checklists.review_bridge.checklist_plan',return_value=ready), patch('apps.api.tasks.checklist_tasks.review_bridge.register_request',side_effect=[None,{'ok':True}]) as register:
        prepare_checklist.run(str(row.id))
        assert durable['status']=='ready'
        assert durable['registered_at'] is None
        vars(row).update(deepcopy(durable))
        from datetime import datetime, timedelta, timezone
        assert row.next_registration_at > datetime.now(timezone.utc)
        row.next_registration_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        prepare_checklist.run(str(row.id))
        assert durable['registered_at'] is not None
        assert register.call_args.kwargs['checklist']['content_sha256']=='b'*64
        assert register.call_count==2


def test_registration_has_separate_bounded_retry_and_strips_customer_trello_url():
    from apps.api.tasks.checklist_tasks import _register
    row=_task_row(); row.registered_at=None; row.snapshot=None;row.trello_card_id=None
    row.intent['brief_url']='https://trello.com/c/PRIVATE1'
    db=MagicMock()
    with patch('apps.api.tasks.checklist_tasks.review_bridge.register_request',return_value=None) as register:
        for _ in range(5):
            row.next_registration_at=None  # Each iteration represents a later recovery tick.
            _register(db,row)
        assert register.call_count==3
        assert row.registration_attempts==3
        assert row.registration_error=='registration-unavailable'
        assert row.next_registration_at is None
        assert register.call_args.args[4]==''


def test_deleted_parent_retires_plan_and_registration_work():
    from apps.api.tasks.checklist_tasks import prepare_checklist
    db=MagicMock();row=_task_row();row.registered_at=None
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value=row
    db.query.return_value.filter.return_value.first.return_value=None
    with patch('apps.api.tasks.checklist_tasks.SessionLocal',return_value=db),patch('apps.api.tasks.checklist_tasks.review_bridge.register_request') as register:
        prepare_checklist.run(str(row.id))
        assert row.status=='failed' and row.error_code=='assignment-unavailable'
        assert row.registration_attempts==3
        db.commit.assert_called()
        register.assert_not_called()


def test_legacy_adoption_uses_verified_card_mapping_without_provider_read():
    from apps.api.routers.folders import create_folder
    from apps.api.schemas.folder import FolderCreate
    from apps.api.services.checklists import binding_for_folder
    project_id=uuid.uuid4();card='0123456789abcdef01234567'
    binding=SimpleNamespace(id=uuid.uuid4(),project_id=project_id,folder_id=None,review_share_token=None,
        request_id=None,trello_card_id=card,intent={'brief_url':f'https://trello.com/c/{card}','trello_short_link':'AbCd1234'})
    folder=SimpleNamespace(id=uuid.uuid4(),project_id=project_id,description='https://trello.com/c/AbCd1234/title')
    db=MagicMock();db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value=binding
    assert binding_for_folder(db,binding.id,project_id,folder.description) is binding
    with patch('apps.api.routers.folders.require_project_role'),patch('apps.api.routers.folders._get_folder',return_value=folder),patch('apps.api.routers.folders._folder_to_response',return_value={'id':str(folder.id)}),patch('apps.api.services.checklists.dispatch_binding'),patch('apps.api.services.review_bridge.checklist_card',return_value=None) as lookup:
        result=create_folder(project_id,FolderCreate(name='Card',checklist_binding_id=binding.id,existing_folder_id=folder.id,description=f'https://trello.com/c/{card}'),db,SimpleNamespace(is_staff=True))
        assert result['id']==str(folder.id)
        lookup.assert_not_called()


@pytest.mark.parametrize('deleted_project',[False,True])
def test_request_listing_hides_checklists_from_revoked_member_or_deleted_project(deleted_project):
    from apps.api.routers.requests import list_requests
    from apps.api.models.upload_request import UploadRequest
    from apps.api.models.project import Project,ProjectMember
    from apps.api.models.checklist_binding import ChecklistBinding
    user=SimpleNamespace(id=uuid.uuid4(),is_staff=False,is_superadmin=False)
    project=SimpleNamespace(id=uuid.uuid4(),name='Private',deleted_at=None)
    req=UploadRequest(id=uuid.uuid4(),token='existing',project_id=project.id,folder_id=uuid.uuid4(),created_by=user.id,title='Private',review_share_token='share')
    binding=SimpleNamespace(id=uuid.uuid4(),request_id=req.id)
    db=MagicMock()
    def query(model):
        q=MagicMock()
        values=[] if model is ProjectMember else [req] if model is UploadRequest else ([] if deleted_project else [project]) if model is Project else [binding] if model is ChecklistBinding else []
        q.filter.return_value=q
        q.order_by.return_value=q
        q.limit.return_value=q
        q.all.return_value=values
        return q
    db.query.side_effect=query
    with patch('apps.api.routers.requests.require_project_role',side_effect=HTTPException(403,'Not a member')),patch('apps.api.routers.requests.review_bridge.request_status',return_value={}),patch('apps.api.routers.requests.review_bridge.asset_stats',return_value={}),patch('apps.api.routers.requests._submitted_assets',return_value=[]),patch('apps.api.routers.requests._review_assets',return_value=[]),patch('apps.api.routers.requests.binding_out',return_value={'private':'criteria'}):
        assert list_requests(None,db,user)==[]
