import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.api.tests.test_iterations import manifest


def ready_state():
    return {'submitted':True,'slots':{s['id']:{'asset_id':str(uuid.uuid4()),'version_id':s['id']+'-v1','version_number':1,'status':'ready'}
        for s in manifest()['slots']}}


def request(state):
    return SimpleNamespace(id=uuid.uuid4(),project_id=uuid.uuid4(),folder_id=uuid.uuid4(),iteration_manifest=manifest(),
        iteration_ratio='9:16',iteration_state=state,iteration_lease_token=None,iteration_lease_until=None,
        revoked_at=None,expires_at=None,review_share_token='source')


def test_claimed_reviews_are_skipped_and_expire():
    from apps.api.services.iteration_flow import active_reviews, next_action
    state=ready_state()
    state['slots']['opening-a']['review_claim']={'token':'t','until':100}
    assert next_action('r',manifest(),state,'9:16',50)['slot_id']=='opening-b'
    assert active_reviews(state,50)==1 and active_reviews(state,100)==0
    assert next_action('r',manifest(),state,'9:16',100)['slot_id']=='opening-a'
    assert next_action('r',manifest(),state,'9:16',50,reviews=False) is None


def test_full_review_slots_still_allow_a_render():
    from apps.api.services.iteration_flow import next_action
    state=ready_state()
    for s in state['slots'].values(): s['status']='clear'
    state['outputs']={}
    first=next_action('r',manifest(),state,'9:16',0)
    state['outputs'][first['key']]={'job_id':'j','asset_id':'a','status':'reviewing'}
    assert next_action('r',manifest(),state,'9:16',0)['kind']=='review_output'
    assert next_action('r',manifest(),state,'9:16',0,reviews=False)['kind']=='render'


def run_step_with(monkeypatch, req, limit=6):
    from apps.api.services import iteration_runner as runner
    from apps.api.tasks import iteration_tasks
    sent=[]
    monkeypatch.setattr(runner.settings,'iteration_parallel_reviews',limit)
    monkeypatch.setattr(runner,'claim',lambda db,rid:'lease')
    monkeypatch.setattr(runner,'locked_request',lambda db,rid:req)
    monkeypatch.setattr(runner,'live_project',lambda db,r:True)
    monkeypatch.setattr(runner,'refresh_sources',lambda db,r,state:[])
    monkeypatch.setattr(runner,'perform',lambda *a:(_ for _ in ()).throw(AssertionError('review must not run inside the request lease')))
    monkeypatch.setattr(iteration_tasks.review_iteration_step,'apply_async',lambda args:sent.append(args))
    return runner.run_step(MagicMock(),req.id),sent


def test_run_step_hands_each_review_to_its_own_task_up_to_the_limit(monkeypatch):
    req=request(ready_state())
    changed,sent=run_step_with(monkeypatch,req,limit=2)
    assert changed is True and req.iteration_lease_token is None
    changed,sent2=run_step_with(monkeypatch,req,limit=2)
    assert changed is True
    claimed=[k for k,v in req.iteration_state['slots'].items() if 'review_claim' in v]
    assert claimed==['opening-a','opening-b']
    assert [a[1]['slot_id'] for a in sent+sent2]==['opening-a','opening-b']
    assert sent[0][2]==req.iteration_state['slots']['opening-a']['review_claim']['token']
    changed,sent3=run_step_with(monkeypatch,req,limit=2)
    assert changed is False and sent3==[]  # third part waits for a free review slot


def run_review_with(monkeypatch, req, effect):
    from apps.api.services import iteration_runner as runner
    monkeypatch.setattr(runner,'locked_request',lambda db,rid:req)
    monkeypatch.setattr(runner,'live_project',lambda db,r:True)
    monkeypatch.setattr(runner,'refresh_sources',lambda db,r,state:[])
    monkeypatch.setattr(runner,'perform',lambda db,r,a:effect)
    db=MagicMock(); db.query.return_value.filter.return_value.first.return_value=req
    return runner


def test_review_result_applies_only_with_the_current_claim(monkeypatch):
    state=ready_state()
    state['slots']['opening-a']['review_claim']={'token':'mine','until':10**12}
    req=request(state)
    runner=run_review_with(monkeypatch,req,{'status':'clear','findings':[],'review_key':'k','version_id':'opening-a-v1'})
    db=MagicMock(); db.query.return_value.filter.return_value.first.return_value=req
    action={'kind':'review_part','slot_id':'opening-a','version_id':'opening-a-v1','review_generation':0}
    assert runner.run_review(db,req.id,action,'other') is False
    assert req.iteration_state['slots']['opening-a']['status']=='ready'
    assert runner.run_review(db,req.id,action,'mine') is True
    slot=req.iteration_state['slots']['opening-a']
    assert slot['status']=='clear' and 'review_claim' not in slot


def test_replaced_upload_drops_the_claim_and_discards_the_old_result(monkeypatch):
    state=ready_state()
    state['slots']['opening-a']['review_claim']={'token':'mine','until':10**12}
    req=request(state)
    runner=run_review_with(monkeypatch,req,{'status':'clear','findings':[],'review_key':'k','version_id':'opening-a-v1'})
    req.iteration_state['slots']['opening-a'].update(version_id='opening-a-v2')
    req.iteration_state['slots']['opening-a'].pop('review_claim')  # what refresh_sources does on a replacement
    db=MagicMock(); db.query.return_value.filter.return_value.first.return_value=req
    action={'kind':'review_part','slot_id':'opening-a','version_id':'opening-a-v1','review_generation':0}
    assert runner.run_review(db,req.id,action,'mine') is False
    assert req.iteration_state['slots']['opening-a']['status']=='ready'


def test_refresh_sources_drops_claim_on_new_version(monkeypatch):
    from apps.api.services import iteration_runner as runner
    from apps.api.models.asset import ProcessingStatus
    state=ready_state(); slot=state['slots']['opening-a']; slot['review_claim']={'token':'t','until':10**12}
    req=request(state)
    asset=SimpleNamespace(folder_id=req.folder_id)
    version=SimpleNamespace(id=uuid.uuid4(),version_number=2,processing_status=ProcessingStatus.processing,
        iteration_review_ready=False,created_at=SimpleNamespace(timestamp=lambda:10**12))
    db=MagicMock(); q=db.query.return_value.filter.return_value
    q.first.return_value=asset; q.order_by.return_value.first.return_value=version
    req.iteration_manifest=None
    runner.refresh_sources(db,req,state)
    assert 'review_claim' not in slot and slot['version_id']==str(version.id)


def test_iteration_tasks_follow_the_configured_queue():
    from apps.api.tasks.celery_app import celery_app
    from apps.api.config import settings
    routes=celery_app.conf.task_routes
    for name in ('advance_iteration_request','review_iteration_step','sweep_iteration_requests','prepare_checklist','resume_checklists'):
        assert routes[name]=={'queue':settings.iteration_queue}
