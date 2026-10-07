"""Preserve upload-operation identity and the original private download container."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest


def test_internal_parts_creation_forwards_one_retry_identity(monkeypatch):
    from apps.api.routers import iterations, requests
    project=SimpleNamespace(id=uuid.uuid4(),is_workspace=True)
    req=SimpleNamespace(iteration_state={})
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=project
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value=None
    lock=MagicMock(return_value=req);monkeypatch.setattr(iterations,'locked_request',lock)
    monkeypatch.setattr(iterations,'require_project_role',lambda *a:None)
    monkeypatch.setattr(iterations.review_bridge,'_call',lambda *a,**k:{'name':'Card'})
    seen=[]
    def create(body,*a):seen.append(body.idempotency_key);return {'id':str(uuid.uuid4()),'url':'https://example.test/r/one'}
    monkeypatch.setattr(requests,'create_request',create)
    key=uuid.uuid4();body=iterations.Handin(project_id=project.id,card_url='https://trello.com/c/AbCd1234',idempotency_key=key)
    for _ in range(2):iterations.create_handin(body,db,SimpleNamespace(is_staff=True,id=uuid.uuid4(),name='Editor',email='editor@example.test'))
    assert seen==[key,key]
    assert lock.call_count==2


@pytest.mark.parametrize('next_name',[None,'Renamed live card'])
def test_internal_parts_retry_preserves_saved_title_when_card_lookup_changes(monkeypatch,next_name):
    from apps.api.routers import iterations, requests
    project=SimpleNamespace(id=uuid.uuid4(),is_workspace=True)
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=project
    saved=[]
    db.query.return_value.filter.return_value.with_for_update.return_value.first.side_effect=lambda:saved[0] if saved else None
    monkeypatch.setattr(iterations,'require_project_role',lambda *a:None)
    monkeypatch.setattr(iterations,'locked_request',lambda *a:SimpleNamespace(iteration_state={}))
    lookup=MagicMock(side_effect=[{'name':'Original card'},({'name':next_name} if next_name else None)])
    monkeypatch.setattr(iterations.review_bridge,'_call',lookup)
    calls=[]
    def create(body,*a):
        calls.append(body)
        if not saved:saved.append(SimpleNamespace(intent={'title':body.title}))
        return {'id':str(uuid.uuid4()),'url':'https://example.test/r/one'}
    monkeypatch.setattr(requests,'create_request',create)
    key=uuid.uuid4();user=SimpleNamespace(is_staff=True,id=uuid.uuid4(),name='Editor',email='editor@example.test')
    for card in ('AbCd1234','AbCd1234','XyZa1234'):
        iterations.create_handin(iterations.Handin(project_id=project.id,card_url=f'https://trello.com/c/{card}',idempotency_key=key),db,user)
    assert [c.title for c in calls]==['Original card']*3
    assert calls[0].brief_url==calls[1].brief_url and calls[2].brief_url!=calls[0].brief_url
    assert lookup.call_count==1


@pytest.mark.parametrize('filename,mime',[('Original cut.mov','video/quicktime'),('Clip.webm','video/webm')])
def test_private_original_keeps_its_container_and_filename(monkeypatch,filename,mime):
    import httpx
    from apps.api.routers import iterations
    monkeypatch.setattr(iterations,'project_scope',lambda *a:{})
    monkeypatch.setattr(iterations.iteration_mixer,'connection',lambda *a:('https://mixer.example/part',{}))
    response=httpx.Response(200,headers={'content-type':mime,'content-disposition':f'attachment; filename="{filename}"'},content=b'original',request=httpx.Request('GET','https://mixer.example/part'))
    client=MagicMock();client.send.return_value=response
    monkeypatch.setattr(httpx,'Client',lambda **k:client)
    result=iterations.owner_part_file(uuid.uuid4(),uuid.uuid4(),MagicMock(),SimpleNamespace())
    assert result.headers['content-type']==mime
    from urllib.parse import quote
    assert quote(filename,safe='') in result.headers['content-disposition']


def test_native_parts_wait_for_persisted_binding_before_any_worker_registration(monkeypatch):
    from apps.api.services import iteration_runner as runner
    slot={'id':'hook','role':'hook','script':'','group':''}
    req=SimpleNamespace(id=uuid.uuid4(),project_id=uuid.uuid4(),folder_id=uuid.uuid4(),iteration_state={'slots':{'hook':{'asset_id':str(uuid.uuid4()),'version_id':str(uuid.uuid4()),'version_number':1}}},iteration_manifest={'summary':'One ad'},brand_slug='brand',title='Review',iteration_brief='Brief',review_share_token='share')
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=None
    registered=[]
    monkeypatch.setattr(runner.review_bridge,'register_request',lambda *a,**k:registered.append(k) or {'ok':True,'brief_status':'ready','brand':'brand'})
    monkeypatch.setattr(runner.review_bridge,'review_iteration',lambda payload:{'status':'clear','review_key':payload['review_key'],'version_id':payload['version_id'],'findings':[]})
    with pytest.raises(RuntimeError,match='saved checklist'):
        runner.perform(db,req,{'kind':'review_part','slot':slot})
    assert registered==[]


def test_native_parts_registration_uses_frozen_text_and_ref_after_worker_cache_loss(monkeypatch):
    from apps.api.services import iteration_runner as runner
    req=SimpleNamespace(id=uuid.uuid4(),project_id=uuid.uuid4(),folder_id=uuid.uuid4(),brand_slug='brand',title='Review',review_share_token='source',iteration_state={'brief_resolved':True})
    binding=SimpleNamespace(id=uuid.uuid4(),project_id=req.project_id,review_share_token='source',context_sha256='a'*64,plan_id='saved-plan',content_sha256='b'*64,snapshot={'briefing':{'text':'Frozen briefing'}})
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=binding
    calls=[]
    monkeypatch.setattr(runner.review_bridge,'register_request',lambda *a,**kw:calls.append((a,kw)) or {'ok':True,'brief_status':'ready','brand':'brand'})
    assert runner.register(db,req,'derived')=='brand'
    assert calls[0][0][3]=='Frozen briefing'
    assert calls[0][1]['checklist']=={'tenant_id':str(req.project_id),'binding_id':str(binding.id),'context_sha256':'a'*64,'plan_id':'saved-plan','content_sha256':'b'*64}
    assert calls[1][1]['brief_source_token']=='source'
