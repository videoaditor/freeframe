"""Server-owned opt-in remains frozen across retries and transport paths."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


def row(intent):
    from apps.api.services.checklists import snapshot_digest
    return SimpleNamespace(id=uuid.uuid4(), project_id=uuid.uuid4(), intent=intent,
        intent_sha256=snapshot_digest(intent), deleted_at=None)


def test_frozen_registration_identity_is_binding_not_upload():
    from apps.api.services.checklists import registration_options
    b = row({'brand':'demo', 'review_engine':'continuity-v1'})
    b.request_id = uuid.uuid4()
    assert registration_options(b) == {'engine':'continuity-v1', 'tenant_id':str(b.project_id), 'request_id':str(b.id)}
    assert registration_options(row({'brand':'demo'})) == {}


def test_unknown_frozen_selector_fails_closed():
    from apps.api.services.checklists import registration_options
    with pytest.raises(ValueError, match='review-engine-invalid'):
        registration_options(row({'review_engine':'other'}))


@pytest.mark.parametrize('selected', [False, True])
def test_retry_keeps_insert_winner_after_config_change(selected):
    from apps.api.services.checklists import reserve_binding
    b = row({'brand':'demo', **({'review_engine':'continuity-v1'} if selected else {})})
    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = b
    with patch('apps.api.services.checklists.settings') as config:
        config.bound_review_project_ids = '' if selected else str(b.project_id)
        assert reserve_binding(db,b.project_id,uuid.uuid4(),'request:fixed',{'brand':'demo'}) is b
    assert ('review_engine' in b.intent) == selected


def test_corrupt_stored_intent_rejected_even_if_business_matches():
    from apps.api.services.checklists import reserve_binding
    b = row({'brand':'demo'}); b.intent_sha256 = '0'*64
    db = MagicMock(); db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = b
    with pytest.raises(HTTPException) as exc:
        reserve_binding(db,b.project_id,uuid.uuid4(),'request:fixed',{'brand':'demo'})
    assert exc.value.status_code == 409


def test_business_change_remains_conflict():
    from apps.api.services.checklists import reserve_binding
    b = row({'brand':'demo', 'review_engine':'continuity-v1'})
    db = MagicMock(); db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = b
    with pytest.raises(HTTPException) as exc:
        reserve_binding(db,b.project_id,uuid.uuid4(),'request:fixed',{'brand':'changed'})
    assert exc.value.status_code == 409


def test_bridge_preserves_current_arguments_and_adds_explicit_identity():
    from apps.api.services.review_bridge import register_request
    with patch('apps.api.services.review_bridge._call', return_value={'ok':True}) as call:
        register_request('s','demo','title','brief','url','pdf',True,'source',checklist={'plan_id':None},
            engine='continuity-v1',tenant_id='P',request_id='B')
    assert call.call_args.kwargs['json'] == {'share_token':'s','brand':'demo','title':'title',
        'brief_text':'brief','brief_url':'url','brief_pdf_base64':'pdf','receive_iterations':True,
        'brief_source_token':'source','checklist':{'plan_id':None},'engine':'continuity-v1','tenant_id':'P','request_id':'B'}


def test_legacy_transport_has_no_engine_identity_fields():
    from apps.api.services.review_bridge import register_request
    with patch('apps.api.services.review_bridge._call') as call:
        register_request('s','demo','title')
    assert not {'engine','tenant_id','request_id'} & call.call_args.kwargs['json'].keys()


def test_snapshot_never_receives_server_selector():
    from apps.api.services.checklists import advance_binding, snapshot_digest
    b=row({'brand':'demo','review_engine':'continuity-v1','brief_text':'Exact text'})
    b.status='queued'; b.next_attempt_at=None; b.attempts=0; b.snapshot=None; b.request_id=None
    b.plan_id=None; b.context_sha256=None
    snapshot={'schema_version':'autoreview.plan-request.v1','tenant_id':str(b.project_id),
        'request_id':str(b.id),'idempotency_key':f'checklist:{b.project_id}:{b.id}'}
    with patch('apps.api.services.checklists.review_bridge.checklist_snapshot',return_value={'snapshot':snapshot,'context_sha256':snapshot_digest(snapshot)}) as source, patch('apps.api.services.checklists.review_bridge.checklist_plan',return_value=None):
        advance_binding(MagicMock(),b)
    assert 'review_engine' not in source.call_args.args[0]
    assert b.intent['review_engine']=='continuity-v1'


def test_outbox_registers_selected_before_plan_ready_without_reselection():
    from apps.api.tasks.checklist_tasks import _register
    b=row({'brand':'demo','review_engine':'continuity-v1'})
    b.registered_at=None; b.review_share_token='s'; b.snapshot=None
    b.context_sha256=b.plan_id=b.content_sha256=None
    with patch('apps.api.tasks.checklist_tasks.review_bridge.register_request',return_value={'ok':True}) as register:
        _register(MagicMock(),b)
    kw=register.call_args.kwargs
    assert kw['engine']=='continuity-v1' and kw['request_id']==str(b.id)
    assert kw['tenant_id']==str(b.project_id)
    assert kw['checklist']['plan_id'] is None


def test_selected_folder_adoption_conflicts_before_binding_mutation():
    from apps.api.routers.folders import create_folder
    from apps.api.schemas.folder import FolderCreate
    b=row({'review_engine':'continuity-v1'}); b.folder_id=None; b.review_share_token=None
    folder=SimpleNamespace(id=uuid.uuid4(),project_id=b.project_id,description='https://trello.com/c/AbCd1234')
    db=MagicMock(); db.query.return_value.filter.return_value.first.return_value=SimpleNamespace(token='legacy')
    db.query.return_value.filter.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value=SimpleNamespace(review_brand_binding=None)
    with patch('apps.api.routers.folders.require_project_role'), patch('apps.api.services.checklists.binding_for_folder',return_value=b), patch('apps.api.routers.folders._get_folder',return_value=folder):
        with pytest.raises(HTTPException) as error:
            create_folder(b.project_id,FolderCreate(name='Card',description=folder.description,checklist_binding_id=b.id,existing_folder_id=folder.id),db,SimpleNamespace(is_staff=True))
    assert error.value.status_code==409
    assert b.folder_id is None and b.review_share_token is None
    db.commit.assert_not_called()


@pytest.mark.parametrize('selected',[False,True])
def test_new_folder_selected_uses_outbox_legacy_still_announces(selected):
    from apps.api.routers.folders import create_folder
    from apps.api.schemas.folder import FolderCreate
    b=row({'review_engine':'continuity-v1'} if selected else {}); b.folder_id=None
    db=MagicMock(); link=SimpleNamespace(token='new-share')
    db.query.return_value.filter.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value=SimpleNamespace(review_brand_binding=None)
    with patch('apps.api.routers.folders.require_project_role'), patch('apps.api.services.checklists.binding_for_folder',return_value=b), patch('apps.api.routers.folders._check_folder_description_requirement'), patch('apps.api.routers.folders._folder_to_response',return_value={}), patch('apps.api.routers.folders.automation_share.create_standing_folder_link',return_value=link), patch('apps.api.routers.folders.automation_share.announce_folder') as announce, patch('apps.api.services.checklists.dispatch_binding') as dispatch:
        create_folder(b.project_id,FolderCreate(name='Card',checklist_binding_id=b.id,description='https://trello.com/c/AbCd1234'),db,SimpleNamespace(is_staff=True,id=uuid.uuid4()))
    assert announce.call_count == (0 if selected else 1)
    dispatch.assert_called_once_with(b.id)
    assert b.review_share_token=='new-share'


def test_derived_registration_preserves_binding_selection_and_source():
    from apps.api.services.iteration_runner import register
    b=row({'review_engine':'continuity-v1'}); b.snapshot={'briefing':{'text':'Frozen'}}
    b.context_sha256='a'*64; b.plan_id='q'; b.content_sha256='b'*64; b.review_share_token='original'
    req=SimpleNamespace(id=uuid.uuid4(),project_id=b.project_id,folder_id=uuid.uuid4(),review_share_token='original',brand_slug='demo',title='Title')
    db=MagicMock(); db.query.return_value.filter.return_value.first.return_value=b
    with patch('apps.api.services.iteration_runner.review_bridge.register_request',return_value={'ok':True,'brief_status':'ready'}) as call:
        register(db,req,'derived')
    assert call.call_count==2
    for c in call.call_args_list:
        assert c.kwargs['engine']=='continuity-v1' and c.kwargs['request_id']==str(b.id)
    assert call.call_args.kwargs['brief_source_token']=='original'


def test_mode_change_uses_original_binding_identity():
    from apps.api.routers.iterations import submission_mode, Mode
    b=row({'review_engine':'continuity-v1'}); b.review_share_token='s'
    b.context_sha256='a'*64; b.plan_id='q'; b.content_sha256='b'*64
    req=SimpleNamespace(id=uuid.uuid4(),project_id=b.project_id,folder_id=uuid.uuid4(),review_share_token='s',brand_slug='demo',title='Title',receive_iterations=True,iteration_mode='components',iteration_state={},iteration_brief='brief')
    db=MagicMock()
    with patch('apps.api.routers.iterations._live_request',return_value=req), patch('apps.api.routers.iterations.locked_request',return_value=req), patch('apps.api.routers.iterations.snapshot',return_value={}), patch('apps.api.services.checklists.request_binding',return_value=b), patch('apps.api.routers.iterations.review_bridge.register_request',return_value={'ok':True}) as call:
        db.query.return_value.filter.return_value.first.return_value=None
        submission_mode('t',Mode(mode='complete'),db)
    assert call.call_args.kwargs['request_id']==str(b.id)
    assert call.call_args.kwargs['checklist']['context_sha256']=='a'*64


def test_selected_share_creation_independent_of_legacy_webhook():
    from apps.api.services import automation_share
    db=MagicMock()
    with patch('apps.api.services.automation_share.is_enabled',return_value=False):
        assert automation_share.create_standing_folder_link(db,uuid.uuid4(),uuid.uuid4(),uuid.uuid4()) is None
        link=automation_share.create_standing_folder_link(db,uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),bound_review=True)
    assert link.permission.value=='comment' and link.allow_download and link.visibility=='public'


def test_business_identity_does_not_equate_boolean_and_number():
    from apps.api.services.checklists import reserve_binding
    b=row({'brand':'demo','expires_in_days':True})
    db=MagicMock(); db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value=b
    with pytest.raises(HTTPException) as error:
        reserve_binding(db,b.project_id,uuid.uuid4(),'request:fixed',{'brand':'demo','expires_in_days':1})
    assert error.value.status_code==409


def test_lost_selector_never_silently_downgrades_registration():
    from apps.api.services.checklists import registration_options
    b=row({'review_engine':'continuity-v1'}); b.intent={}
    with pytest.raises(HTTPException) as error: registration_options(b)
    assert error.value.status_code==409
