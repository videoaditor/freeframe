"""Sealed membership, early review and private project-owned handoff."""
from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi import HTTPException


def request():
    return SimpleNamespace(id=uuid.uuid4(),project_id=uuid.uuid4(),created_by=uuid.uuid4(),iteration_owner_id=uuid.uuid4(),
        receive_iterations=True,iteration_mode='components',iteration_manifest={'schema_version':1,'summary':'All combinations','slots':[],'recipes':[]},
        iteration_state={},iteration_ratio='9:16')


def parts():
    return [{'id':'hook-a','role':'hook','label':'Hook A'},{'id':'hook-b','role':'hook','label':'Hook B'},
            {'id':'body','role':'body','label':'Body'}]


def test_simple_parts_without_script_generate_exact_declared_combinations():
    from apps.api.services.iteration_requests import declare_parts
    req=request(); declare_parts(req,parts())
    assert [r['slots'] for r in req.iteration_manifest['recipes']]==[['hook-a','body'],['hook-b','body']]
    assert all(s['script']=='' for s in req.iteration_manifest['slots'])
    declare_parts(req,parts())
    assert len(req.iteration_manifest['slots'])==3


def test_seal_refuses_partial_bytes_and_freezes_membership():
    from apps.api.services.iteration_requests import declare_parts, seal, snapshot
    req=request(); declare_parts(req,parts())
    req.iteration_state={'slots':{s['id']:{'status':'clear','version_id':s['id'],'bytes_stored':True} for s in parts()[:2]}}
    with pytest.raises(HTTPException): seal(req)
    assert not snapshot(req)['can_leave']
    req.iteration_state['slots']['body']={'status':'processing','version_id':'body','bytes_stored':True}
    seal(req); seal(req)
    assert snapshot(req)['submitted'] and snapshot(req)['can_leave'] and not snapshot(req)['editor_done']
    with pytest.raises(HTTPException): declare_parts(req,[{'id':'late','role':'hook','label':'Late'}])


def test_unsealed_all_clear_cannot_render_but_can_review_ready_part():
    from apps.api.services.iteration_requests import declare_parts
    from apps.api.services.iteration_flow import next_action
    req=request();declare_parts(req,parts())
    req.iteration_state={'slots':{s['id']:{'status':'clear','version_id':s['id']} for s in parts()}}
    assert next_action(str(req.id),req.iteration_manifest,req.iteration_state,'9:16',0) is None
    req.iteration_state['slots']['hook-a']['status']='ready'
    assert next_action(str(req.id),req.iteration_manifest,req.iteration_state,'9:16',0)['kind']=='review_part'


def test_eligible_recipe_precedes_unrelated_part_review():
    from apps.api.services.iteration_requests import declare_parts
    from apps.api.services.iteration_flow import next_action
    req=request();declare_parts(req,parts())
    req.iteration_state={'submitted':True,'slots':{s['id']:{'status':'clear','version_id':s['id']} for s in parts()}}
    req.iteration_state['slots']['hook-a']['status']='ready'
    action=next_action(str(req.id),req.iteration_manifest,req.iteration_state,'9:16',0)
    assert action['kind']=='render' and action['recipe']['slots']==['hook-b','body']


def test_owner_scope_is_frozen_project_owner_never_uploader():
    from apps.api.services.iteration_runner import identity
    req=request()
    assert identity(req)['owner_id']==f'freeframe:{req.iteration_owner_id}'
    req.iteration_owner_id=None
    with pytest.raises(RuntimeError): identity(req)


def test_bound_slot_revision_requires_explicit_same_asset():
    from apps.api.services.iteration_requests import declare_parts, revision_target
    req=request();declare_parts(req,parts());asset=str(uuid.uuid4())
    req.iteration_state={'slots':{'body':{'asset_id':asset,'version_id':'v'}}}
    with pytest.raises(HTTPException):revision_target(req,'body',None)
    with pytest.raises(HTTPException):revision_target(req,'body',uuid.uuid4())
    assert revision_target(req,'body',uuid.UUID(asset))==asset


def test_foreign_owner_cannot_read_private_parts(monkeypatch):
    from apps.api.routers import iterations
    req=request();db=MagicMock();project=SimpleNamespace(id=req.project_id,created_by=req.iteration_owner_id)
    db.query.return_value.filter.return_value.first.return_value=project
    def deny(*args):raise HTTPException(403,'Requires owner')
    monkeypatch.setattr(iterations,'require_project_role',deny)
    with pytest.raises(HTTPException):iterations.owner_parts(req.project_id,db,SimpleNamespace(id=req.created_by))


def test_unsealed_or_partial_progress_never_reports_batch_delivered():
    from apps.api.services.iteration_requests import declare_parts,snapshot
    from apps.api.services.iteration_flow import current_recipes
    req=request();declare_parts(req,parts())
    req.iteration_state={'slots':{s['id']:{'status':'clear','version_id':s['id'],'bytes_stored':True} for s in parts()}}
    req.iteration_state['outputs']={k:{'status':'delivered'} for _,k in current_recipes(str(req.id),req.iteration_manifest,req.iteration_state,'9:16')}
    result=snapshot(req)
    assert result['state']!='delivered' and not result['editor_done']


def test_explicit_missing_version_never_falls_back_to_old_ready_media(monkeypatch):
    from apps.api.routers import share
    asset=SimpleNamespace(id=uuid.uuid4(),asset_type='video');link=SimpleNamespace(allow_download=True,show_versions=False)
    monkeypatch.setattr(share,'validate_share_link_with_session',lambda *a,**kw:link)
    monkeypatch.setattr(share,'_get_asset',lambda *a:asset)
    monkeypatch.setattr(share,'validate_asset_in_share',lambda *a:None)
    monkeypatch.setattr(share,'_get_latest_media_file',lambda *a:pytest.fail('Exact version must not fall back'))
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=None
    with pytest.raises(HTTPException) as error:
        share.get_share_stream_url('share',asset.id,version_id=uuid.uuid4(),share_session=None,download=True,db=db,current_user=None)
    assert error.value.status_code==404


def test_ai_proxy_echoes_exact_requested_version_or_refuses(monkeypatch):
    from apps.api.routers import share
    asset=SimpleNamespace(id=uuid.uuid4(),asset_type='video');link=SimpleNamespace()
    monkeypatch.setattr(share,'validate_share_link_with_session',lambda *a,**kw:link)
    monkeypatch.setattr(share,'_get_asset',lambda *a:asset)
    monkeypatch.setattr(share,'validate_asset_in_share',lambda *a:None)
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=None
    with pytest.raises(HTTPException) as error:
        share.get_share_ai_proxy_url('share',asset.id,version_id=uuid.uuid4(),share_session=None,db=db,current_user=None)
    assert error.value.status_code==404


def test_validated_original_review_overlaps_playback_transcode():
    from apps.api.services.iteration_runner import refresh_sources
    from apps.api.models.asset import ProcessingStatus
    from datetime import datetime,timezone
    req=request();asset=SimpleNamespace(id=uuid.uuid4(),folder_id=uuid.uuid4())
    req.folder_id=asset.folder_id
    version=SimpleNamespace(id=uuid.uuid4(),version_number=1,processing_status=ProcessingStatus.processing,
        iteration_review_ready=True,created_at=datetime.now(timezone.utc))
    state={'slots':{'hook':{'asset_id':str(asset.id),'version_id':str(version.id),'status':'processing','bytes_stored':True}}}
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=asset
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value=version
    refresh_sources(db,req,state)
    assert state['slots']['hook']['status']=='ready'


def test_internal_delivery_requires_whole_sealed_batch_and_retries_service_failure():
    from apps.api.services.iteration_requests import declare_parts
    from apps.api.services.iteration_flow import next_action,current_recipes,action_current
    req=request();declare_parts(req,parts())
    state={'submitted':True,'internal_handin':{'card_url':'https://trello.com/c/AbCd1234'},
        'slots':{s['id']:{'status':'clear','version_id':s['id']} for s in parts()}}
    keys=[k for _,k in current_recipes(str(req.id),req.iteration_manifest,state,'9:16')]
    state['outputs']={k:{'status':'delivered'} for k in keys}
    action=next_action(str(req.id),req.iteration_manifest,state,'9:16',0)
    assert action['kind']=='deliver_batch'
    assert action_current(str(req.id),req.iteration_manifest,state,'9:16',action)
    state['outputs'][keys[1]]['status']='held'
    assert not action_current(str(req.id),req.iteration_manifest,state,'9:16',action)
    state['outputs'][keys[1]]['status']='delivered';state['submitted']=False
    assert next_action(str(req.id),req.iteration_manifest,state,'9:16',0) is None


def test_delivery_failure_does_not_display_whole_batch_success():
    from apps.api.services.iteration_requests import declare_parts,snapshot
    from apps.api.services.iteration_flow import current_recipes
    req=request();declare_parts(req,parts())
    req.iteration_state={'submitted':True,'internal_handin':{},'delivery':{'status':'error'},
        'slots':{s['id']:{'status':'clear','version_id':s['id'],'bytes_stored':True} for s in parts()}}
    req.iteration_state['outputs']={k:{'status':'delivered'} for _,k in current_recipes(str(req.id),req.iteration_manifest,req.iteration_state,'9:16')}
    assert snapshot(req)['state']=='error'


def test_busy_transcode_is_not_duplicated_by_iteration_reconciliation(monkeypatch):
    from apps.api.services.iteration_runner import refresh_sources
    from apps.api.tasks import cleanup_tasks
    from apps.api.models.asset import ProcessingStatus
    from datetime import datetime,timezone,timedelta
    version=SimpleNamespace(id=uuid.uuid4(),version_number=1,processing_status=ProcessingStatus.processing,
        created_at=datetime.now(timezone.utc)-timedelta(minutes=20))
    asset=SimpleNamespace(id=uuid.uuid4(),folder_id=uuid.uuid4())
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=asset
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value=version
    state={'slots':{'hook':{'asset_id':str(asset.id),'version_id':str(version.id),'status':'processing'}}}
    monkeypatch.setattr(cleanup_tasks,'_known_job_version_ids',lambda:{str(version.id)})
    assert refresh_sources(db,SimpleNamespace(folder_id=asset.folder_id),state)==[]


def test_public_share_validation_cannot_leak_source_stream(monkeypatch):
    from apps.api.routers import share
    asset=SimpleNamespace(id=uuid.uuid4(),project_id=uuid.uuid4(),folder_id=uuid.uuid4(),iteration_source=True)
    link=SimpleNamespace(token='public',visibility='public',folder_id=None,project_id=None,password_hash=None,asset_id=asset.id)
    monkeypatch.setattr(share,'validate_share_link',lambda *a:link)
    monkeypatch.setattr(share,'_get_asset',lambda *a:asset)
    monkeypatch.setattr(share,'_get_latest_media_file',lambda *a:pytest.fail('Private stream was read before authorization'))
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=None
    with pytest.raises(HTTPException) as error:share.validate_share_link_endpoint('public',db=db,current_user=None)
    assert error.value.status_code==403


def test_hook_replacement_withdraws_only_dependent_released_output():
    from apps.api.services.iteration_requests import declare_parts,bind_upload
    from apps.api.services.iteration_flow import current_recipes
    req=request();declare_parts(req,parts())
    req.iteration_state={'submitted':True,'slots':{s['id']:{'asset_id':str(uuid.uuid4()),'version_id':str(uuid.uuid4()),'status':'clear'} for s in parts()}}
    outputs={k:{'status':'delivered','asset_id':str(uuid.uuid4())} for _,k in current_recipes(str(req.id),req.iteration_manifest,req.iteration_state,'9:16')}
    req.iteration_state['outputs']=outputs
    released=SimpleNamespace(iteration_pending=False,folder_id=uuid.uuid4())
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=released
    slot=req.iteration_manifest['slots'][0]
    bind_upload(req,slot,SimpleNamespace(id=uuid.uuid4()),SimpleNamespace(id=uuid.uuid4(),version_number=2),db)
    assert released.iteration_pending is True and released.folder_id is None
    assert db.query.call_count==1


def test_explicit_retry_changes_review_key_generation_without_invalidating_clear_parts(monkeypatch):
    from apps.api.routers import iterations
    req=request();req.iteration_state={'slots':{'hook':{'status':'error','attempts':3},'body':{'status':'clear'}},
        'outputs':{'ad':{'status':'error','attempts':3}}}
    monkeypatch.setattr(iterations,'_live_request',lambda *a:req)
    monkeypatch.setattr(iterations,'locked_request',lambda *a:req)
    monkeypatch.setattr(iterations,'snapshot',lambda *a:req.iteration_state)
    state=iterations.retry('token',MagicMock())
    assert state['slots']['hook']['review_generation']==1
    assert state['outputs']['ad']['review_generation']==1
    assert state['slots']['body']=={'status':'clear'}


def test_review_from_before_explicit_retry_cannot_apply():
    from apps.api.services.iteration_flow import action_current
    req=request();state={'slots':{'hook':{'version_id':'same','review_generation':1}}}
    assert not action_current(str(req.id),req.iteration_manifest,state,'9:16',
        {'kind':'review_part','slot_id':'hook','version_id':'same','review_generation':0})


def test_policy_conflict_reopens_final_reviews_and_withdraws_public_outputs():
    from apps.api.services.iteration_requests import declare_parts
    from apps.api.services.iteration_flow import current_recipes
    from apps.api.services.iteration_runner import apply_effect
    req=request();declare_parts(req,parts());req.iteration_state={'submitted':True,'delivery':{'started':True},
        'slots':{s['id']:{'version_id':s['id'],'status':'clear'} for s in parts()}}
    keys=[k for _,k in current_recipes(str(req.id),req.iteration_manifest,req.iteration_state,'9:16')]
    req.iteration_state['outputs']={k:{'status':'delivered','asset_id':str(uuid.uuid4()),'review_key':'old'} for k in keys}
    asset=SimpleNamespace(iteration_pending=False,folder_id=uuid.uuid4());db=MagicMock();db.query.return_value.filter.return_value.first.return_value=asset
    apply_effect(db,req,{'kind':'deliver_batch','keys':keys},{'status':'error','review_conflict':True})
    assert not req.iteration_state['delivery']['started']
    assert all(o['status']=='reviewing' and o['review_generation']==1 for o in req.iteration_state['outputs'].values())
    assert asset.iteration_pending and asset.folder_id is None


def test_generic_mutation_refuses_iteration_managed_media():
    from apps.api.services.iteration_requests import require_unmanaged
    for field in ('iteration_source','iteration_derived','iteration_pending'):
        with pytest.raises(HTTPException):require_unmanaged(SimpleNamespace(**{field:True}))
    require_unmanaged(SimpleNamespace())


@pytest.mark.parametrize('endpoint',['upload','versions'])
def test_generic_version_routes_enforce_managed_guard(endpoint,monkeypatch):
    from apps.api.routers import upload,assets
    from apps.api.schemas.upload import InitiateUploadRequest
    project_id=uuid.uuid4();asset=SimpleNamespace(id=uuid.uuid4(),project_id=project_id,iteration_derived=True)
    db=MagicMock();db.query.return_value.filter.return_value.first.side_effect=([SimpleNamespace(id=project_id),asset] if endpoint=='upload' else [asset])
    module=upload if endpoint=='upload' else assets
    monkeypatch.setattr(module,'require_project_role',lambda *a:None)
    monkeypatch.setattr(module,'upload_guard_error',lambda *a:None)
    body=InitiateUploadRequest(project_id=project_id,asset_id=asset.id,asset_name='overwrite',original_filename='overwrite.mp4',mime_type='video/mp4',file_size_bytes=100)
    with pytest.raises(HTTPException) as error:
        if endpoint=='upload':upload.initiate_upload(body,db,SimpleNamespace(id=uuid.uuid4()))
        else:assets.initiate_new_version(asset.id,body,db,SimpleNamespace(id=uuid.uuid4()))
    assert error.value.status_code==409
    db.add.assert_not_called()


def test_generic_folder_upload_cannot_append_to_sealed_batch():
    from apps.api.services.iteration_requests import require_unmanaged_destination
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=SimpleNamespace(receive_iterations=True,iteration_mode='components')
    with pytest.raises(HTTPException):require_unmanaged_destination(db,uuid.uuid4())


def test_generic_move_cannot_detach_managed_output(monkeypatch):
    from apps.api.routers import folders
    from apps.api.schemas.folder import AssetMoveRequest
    asset=SimpleNamespace(id=uuid.uuid4(),project_id=uuid.uuid4(),folder_id=uuid.uuid4(),iteration_derived=True)
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=asset
    monkeypatch.setattr(folders,'require_project_role',lambda *a:None)
    with pytest.raises(HTTPException):folders.move_asset(asset.id,AssetMoveRequest(folder_id=None),db,SimpleNamespace(id=uuid.uuid4()))
    db.commit.assert_not_called()


def test_abort_first_attempt_detaches_only_its_binding_and_keeps_structured_slot():
    from apps.api.services.iteration_requests import aborted_upload
    req=request();req.iteration_manifest['slots']=[{'id':'body','role':'body','label':'Body'}]
    req.iteration_state={'structured':True,'slots':{'body':{'asset_id':'asset','version_id':'v1','status':'uploading'}}}
    aborted_upload(req,SimpleNamespace(id='v1',asset_id='asset'),None)
    assert req.iteration_manifest['slots'][0]['id']=='body'
    assert 'body' not in req.iteration_state['slots']


def test_aborted_revision_rebinds_prior_bytes_without_restoring_approval():
    from apps.api.services.iteration_requests import aborted_upload
    req=request();req.iteration_state={'submitted':True,'slots':{'body':{'asset_id':'asset','version_id':'v2','status':'uploading'}}}
    aborted_upload(req,SimpleNamespace(id='v2',asset_id='asset'),SimpleNamespace(id='v1',version_number=1),True)
    source=req.iteration_state['slots']['body']
    assert source['version_id']=='v1' and source['status']=='processing' and source['bytes_stored'] is True


def test_every_iteration_registration_inherits_original_brief(monkeypatch):
    from apps.api.services import iteration_runner,review_bridge
    req=request();req.iteration_state={'brief_resolved':True};req.review_share_token='original';req.brand_slug='brand';req.title='Title';req.iteration_brief=''
    calls=[]
    monkeypatch.setattr(review_bridge,'register_request',lambda *a,**kw:calls.append(kw) or {'ok':True,'brand':'brand','brief_status':'ready'})
    iteration_runner.register(req,'original');iteration_runner.register(req,'final')
    assert all(c['brief_source_token']=='original' for c in calls)


def test_pending_brief_inputs_retry_privately_and_are_not_in_progress(monkeypatch):
    from apps.api.services import iteration_runner,review_bridge
    from apps.api.services.iteration_requests import snapshot,request_fields
    req=request();req.review_share_token='original';req.brand_slug='brand';req.title='Title';req.iteration_brief=''
    req.iteration_state={'brief_input':{'url':'https://example.com/brief','pdf':'private-pdf'},'slots':{}}
    calls=[]
    monkeypatch.setattr(review_bridge,'register_request',lambda *a,**kw:calls.append((a,kw)) or {'ok':True,'brand':'brand','brief_status':'ready'})
    iteration_runner.register(req,'original')
    assert calls[0][0][4:6]==('https://example.com/brief','private-pdf')
    assert 'private-pdf' not in str(snapshot(req)) and 'private-pdf' not in str(request_fields(req))


@pytest.mark.parametrize('current',[True,False])
def test_pending_private_brief_is_erased_only_after_current_resolution_acknowledgment(current):
    from apps.api.services.iteration_runner import apply_effect
    req=request();req.iteration_state={'brief_input':{'pdf':'private-pdf'},'slots':{'hook':{'version_id':'v2','status':'ready'}}}
    applied=apply_effect(MagicMock(),req,{'kind':'review_part','slot_id':'hook','version_id':'v2' if current else 'v1'},
        {'status':'clear','findings':[],'brief_resolved':True})
    assert applied is current
    assert ('brief_input' not in req.iteration_state) is current
    assert bool(req.iteration_state.get('brief_resolved')) is current
