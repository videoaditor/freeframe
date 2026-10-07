"""Current Parts/output scope is durable; no project-wide snapshot access."""
import uuid
import pytest
from copy import deepcopy
from apps.api.tests.test_checklist_snapshot_postgres import assignment
from apps.api.models.asset import Asset,AssetVersion,AssetType,ProcessingStatus
from apps.api.models.share import ShareLink
from apps.api.services.iteration_flow import current_recipes


def setup_parts(a):
    db=a['db'];req=a['request'];asset=a['asset'];v=a['later']
    body=Asset(project_id=a['project'].id,folder_id=a['folder'].id,name='Body',created_by=asset.created_by,asset_type=AssetType.video)
    db.add(body);db.flush();body_v=AssetVersion(asset_id=body.id,version_number=1,created_by=asset.created_by,processing_status=ProcessingStatus.ready)
    db.add(body_v);db.flush()
    req.receive_iterations=True;req.iteration_mode='components';req.iteration_manifest={'schema_version':1,'summary':'One combination','slots':[{'id':'hook','role':'hook'},{'id':'body','role':'body'}],'recipes':[{'id':'ad','label':'Ad','slots':['hook','body']}]}
    req.iteration_state={'slots':{'hook':{'asset_id':str(asset.id),'version_id':str(v.id),'status':'clear'},'body':{'asset_id':str(body.id),'version_id':str(body_v.id),'status':'clear'}}}
    db.flush();return req


def read(client,a,asset,version,share):
    return client.get('/internal/review/iteration-checklist-snapshot',params={'binding_id':str(a['binding'].id),'project_id':str(a['project'].id),'asset_id':str(asset),'version_id':str(version),'share_token':share},headers={'Authorization':'Bearer synthetic-bridge-secret'})


def test_parts_snapshot_requires_exact_current_source_and_original_share(client,assignment):
    a=assignment;req=setup_parts(a)
    r=read(client,a,a['asset'].id,a['later'].id,a['share'].token)
    assert r.status_code==200
    assert r.json()['snapshot']==a['snapshot']
    assert read(client,a,a['asset'].id,a['version'].id,a['share'].token).status_code==404
    assert read(client,a,a['other_asset'].id,a['other_version'].id,a['share'].token).status_code==404


def test_derived_output_scope_is_verified_before_folder_publication_and_revoked_on_replacement(client,assignment):
    a=assignment;req=setup_parts(a);db=a['db']
    output=Asset(project_id=a['project'].id,folder_id=None,name='Private assembled ad',created_by=req.created_by,asset_type=AssetType.video,iteration_derived=True,iteration_pending=True)
    db.add(output);db.flush();v=AssetVersion(asset_id=output.id,version_number=1,created_by=req.created_by,processing_status=ProcessingStatus.ready)
    db.add(v);db.flush();share=ShareLink(asset_id=output.id,token='private-output-'+uuid.uuid4().hex,created_by=req.created_by)
    db.add(share);db.flush()
    key=next(current_recipes(str(req.id),req.iteration_manifest,req.iteration_state,req.iteration_ratio))[1]
    state=deepcopy(req.iteration_state);state['outputs']={key:{'asset_id':str(output.id),'version_id':str(v.id),'share_token':share.token,'status':'reviewing'}};req.iteration_state=state;db.flush()
    assert read(client,a,output.id,v.id,share.token).status_code==200
    assert read(client,a,output.id,v.id,a['share'].token).status_code==404
    # A replacement committed before state reconciliation must invalidate the old derived review.
    newer=AssetVersion(asset_id=a['asset'].id,version_number=3,created_by=req.created_by,processing_status=ProcessingStatus.ready)
    db.add(newer);db.flush()
    assert read(client,a,output.id,v.id,share.token).status_code==404
