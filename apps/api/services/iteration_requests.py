"""Projection and upload helpers shared by the request routes and background worker."""
from copy import deepcopy
import uuid

from fastapi import HTTPException

from ..config import settings
from ..models.asset import Asset, AssetStatus, AssetVersion, MediaFile
from ..models.upload_request import UploadRequest
from .iteration_flow import current_recipes, progress
from .review_timing import iteration_review_progress
from . import s3_service


def enabled(req):
    return getattr(req, 'receive_iterations', False) is True


def components(req):
    return enabled(req) and req.iteration_mode == 'components'


def upload_slot(req, slot_id, mime):
    if not components(req):
        if slot_id:
            raise HTTPException(409, 'This request receives complete ads. Refresh before uploading.')
        return None
    slot = next((s for s in req.iteration_manifest['slots'] if s['id'] == slot_id), None)
    if not slot or not mime.startswith('video/'):
        raise HTTPException(400, 'Choose the matching part and upload a video.')
    return slot


def request_fields(req):
    if not enabled(req):
        return {'receive_iterations': False}
    state = req.iteration_state or {}
    slots = [state.get('slots', {}).get(s['id'], {'status':'waiting'}) for s in req.iteration_manifest['slots']]
    outputs = [state.get('outputs', {}).get(key, {}) for _, key in current_recipes(str(req.id), req.iteration_manifest, state, req.iteration_ratio)]
    st = progress(slots, outputs, len(req.iteration_manifest['recipes']))
    if st['state']=='delivered' and 'internal_handin' in state and state.get('delivery',{}).get('status')!='delivered':
        st['state']='error' if state.get('delivery',{}).get('status')=='error' else 'delivering'
    st.update(handoff_state(req))
    if not st['submitted'] and st['state']=='delivered': st['state']='waiting'
    fields = {'receive_iterations': True, 'iteration_manifest':req.iteration_manifest,
              'iteration_mode':req.iteration_mode, 'iteration_status':st}
    if components(req):
        fields.update(status='clear' if st['state']=='delivered' else 'held' if st['state']=='held' else 'reviewing',
                      open_must_fixes=sum(f.get('must_fix', False) for v in slots+outputs for f in v.get('findings', [])))
    return fields


def snapshot(req, db=None):
    manifest = req.iteration_manifest or {'slots':[], 'recipes':[]}
    state = req.iteration_state or {}
    slots = [{'slot_id':s['id'], **state.get('slots', {}).get(s['id'], {'status':'waiting','findings':[]})} for s in manifest['slots']]
    slots = [{k:v for k,v in s.items() if k not in ('render_payload','review_key')} for s in slots]
    if db is not None:
        for entry in slots:
            if entry.get('version_id'):
                entry.update(iteration_review_progress(db, req, entry, source=True))
                media=db.query(MediaFile).filter(MediaFile.version_id==uuid.UUID(entry['version_id'])).first()
                if media:
                    entry['media_url']=s3_service.generate_presigned_get_url(media.s3_key_raw)
                    entry['duration_seconds']=media.duration_seconds
                    entry['thumbnail_url']=s3_service.generate_presigned_get_url(media.s3_key_thumbnail) if media.s3_key_thumbnail else None
                entry['versions']=[{'id':str(v.id),'version_number':v.version_number,'processing':v.processing_status.value}
                    for v in db.query(AssetVersion).filter(AssetVersion.asset_id==uuid.UUID(entry['asset_id']),
                    AssetVersion.deleted_at.is_(None)).order_by(AssetVersion.version_number.desc()).all()]
    outputs=[]
    current = {r['id']:key for r,key in current_recipes(str(req.id),manifest,state,req.iteration_ratio)}
    for recipe in manifest['recipes']:
        key=current.get(recipe['id'])
        data=state.get('outputs',{}).get(key,{})
        item={'id':key or recipe['id'],'recipe_id':recipe['id'],'slot_ids':recipe['slots'],'label':recipe['label'],'status':data.get('status','waiting'),
              'findings':data.get('findings',[])}
        if data.get('error'): item['error']=data['error']
        if data.get('asset_id') and data.get('version_id'):
            item.update(asset_id=data['asset_id'], version_id=data['version_id'], version_number=data.get('version_number',1))
            if db is not None:
                item.update(iteration_review_progress(db, req, data))
        if data.get('status') in ('held','delivered') and data.get('s3_key'):
            item['media_url']=s3_service.generate_presigned_get_url(data['s3_key'])
            if db is not None and data.get('version_id'):
                media=db.query(MediaFile).filter(MediaFile.version_id==uuid.UUID(data['version_id'])).first()
                item['duration_seconds']=media.duration_seconds if media else None
                item['thumbnail_url']=s3_service.generate_presigned_get_url(media.s3_key_thumbnail) if media and media.s3_key_thumbnail else None
        if data.get('status')=='delivered' and data.get('s3_key'):
            item['asset_id']=data['asset_id']
            item['download_url']=s3_service.generate_presigned_get_url(data['s3_key'], download_filename=recipe['label']+'.mp4')
        outputs.append(item)
    status=progress(slots,outputs,len(manifest['recipes']))
    if status['state']=='delivered' and 'internal_handin' in state and state.get('delivery',{}).get('status')!='delivered':
        status['state']='error' if state.get('delivery',{}).get('status')=='error' else 'delivering'
    handoff=handoff_state(req)
    if not handoff['submitted'] and status['state']=='delivered': status['state']='waiting'
    return {'enabled':enabled(req),'mode':req.iteration_mode,'manifest':manifest,'slots':slots,'outputs':outputs,
            **status,**handoff,'simple':not state.get('structured',False),
            'delivery':{k:v for k,v in state.get('delivery',{}).items() if k in ('status','error')},
            'share_url':(settings.frontend_url.rstrip('/')+'/share/'+state['delivery']['share_token']) if state.get('delivery',{}).get('share_token') else None}


def invalidate_outputs(db,req,state,slot_id):
    for recipe,key in current_recipes(str(req.id),req.iteration_manifest,state,req.iteration_ratio):
        output=state.get('outputs',{}).get(key,{})
        if slot_id not in recipe['slots'] or not output.get('asset_id'):continue
        output.update(status='reviewing',review_generation=output.get('review_generation',0)+1,attempts=0,next_attempt_at=0)
        asset=db.query(Asset).filter(Asset.id==uuid.UUID(output['asset_id']),Asset.project_id==req.project_id,Asset.deleted_at.is_(None)).first()
        if asset:
            asset.iteration_pending=True;asset.folder_id=None;asset.status=AssetStatus.in_review


def bind_upload(req, slot, asset, version, db=None):
    state=deepcopy(req.iteration_state or {})
    if db is not None:invalidate_outputs(db,req,state,slot['id'])
    state.setdefault('slots',{})[slot['id']]={'asset_id':str(asset.id),'version_id':str(version.id),
        'version_number':version.version_number,'bytes_stored':False,'status':'uploading','findings':[],'attempts':0}
    req.iteration_state=state


def locked_request(db, request_id):
    return db.query(UploadRequest).filter(UploadRequest.id==request_id).populate_existing().with_for_update().first()


def withdraw_finding(req, asset_id, version_id, comment_id):
    state=deepcopy(req.iteration_state or {})
    for category in ('slots','outputs'):
        for item in state.get(category,{}).values():
            if item.get('asset_id')!=str(asset_id) or item.get('version_id')!=version_id:
                continue
            item['findings']=[f for f in item.get('findings',[]) if f.get('id')!=comment_id]
            if item.get('status')=='held':
                item.update(status='ready' if category=='slots' else 'reviewing',next_attempt_at=0)
    req.iteration_state=state


def declare_parts(req, parts):
    """Add immutable, explicitly labelled inputs; preserve signed constrained plans."""
    from itertools import product
    from .iteration_manifest import digest
    if not components(req): raise HTTPException(409, 'This request receives complete ads.')
    state = req.iteration_state or {}
    manifest = deepcopy(req.iteration_manifest or {'schema_version':1,'summary':'All selected combinations','slots':[],'recipes':[]})
    by_id = {s['id']:s for s in manifest['slots']}
    for part in parts:
        prior = by_id.get(part['id'])
        if prior:
            if any(prior[k] != part[k] for k in ('role','label')):
                raise HTTPException(409, 'A declared part cannot change its role or name.')
            continue
        if state.get('submitted'): raise HTTPException(409, 'This batch is submitted. Replace an existing part instead.')
        if state.get('structured'): raise HTTPException(409, 'Use the parts from the confirmed briefing.')
        by_id[part['id']] = {**part,'group':'Shared','script':''}
    if len(by_id)>40: raise HTTPException(422, 'A batch supports up to 40 unique parts.')
    if not state.get('structured'):
        manifest['slots'] = list(by_id.values())
        stages = [[s for s in by_id.values() if s['role']==r] for r in ('hook','lead','body','cta')]
        combinations = product(stages[0], stages[1] or [None], stages[2], stages[3] or [None])
        recipes=[]
        for combination in combinations:
            selected=[s for s in combination if s]
            ids=[s['id'] for s in selected]
            recipes.append({'id':digest(ids)[:24],'label':' + '.join(s['label'] for s in selected)[:200],'slots':ids})
            if len(recipes)>100: raise HTTPException(422, 'Select fewer parts: at most 100 finished ads per batch.')
        manifest['recipes']=recipes
    req.iteration_manifest=manifest


def handoff_state(req):
    state=req.iteration_state or {};manifest=req.iteration_manifest or {'slots':[],'recipes':[]}
    slots=[state.get('slots',{}).get(s['id'],{}) for s in manifest['slots']]
    submitted=state.get('submitted') is True
    can_leave=submitted and bool(slots) and all(s.get('bytes_stored') is True for s in slots)
    return {'submitted':submitted,'can_leave':can_leave,
            'editor_done':can_leave and all(s.get('status')=='clear' for s in slots)
                and not any(o.get('status')=='held' for _,key in current_recipes(str(req.id),manifest,state,req.iteration_ratio)
                            for o in [state.get('outputs',{}).get(key,{})])}


def seal(req):
    if not components(req): raise HTTPException(409, 'This request receives complete ads.')
    state=deepcopy(req.iteration_state or {});manifest=req.iteration_manifest or {}
    if not manifest.get('recipes'): raise HTTPException(409, 'Add at least one hook and one body before submitting.')
    if not all(state.get('slots',{}).get(s['id'],{}).get('bytes_stored') is True for s in manifest['slots']):
        raise HTTPException(409, 'Wait for every declared file to finish uploading before submitting.')
    state['submitted']=True
    req.iteration_state=state


def revision_target(req,slot_id,asset_id):
    bound=(req.iteration_state or {}).get('slots',{}).get(slot_id,{}).get('asset_id')
    if bound and str(asset_id)!=bound:
        raise HTTPException(409, 'Replace this part explicitly using its current asset_id.')
    if not bound and asset_id:
        raise HTTPException(409, 'This part has no existing file to replace.')
    return bound


def stored_upload(req,version):
    state=deepcopy(req.iteration_state or {})
    for item in state.get('slots',{}).values():
        if item.get('version_id')==str(version.id): item.update(bytes_stored=True,status='processing')
    req.iteration_state=state


def require_unmanaged(asset):
    if any(getattr(asset,flag,False) is True for flag in ('iteration_source','iteration_derived','iteration_pending')):
        raise HTTPException(409,'Use this submission’s Replace action. Assembled outputs cannot be overwritten.')


def require_unmanaged_destination(db,folder_id):
    if folder_id:
        req=db.query(UploadRequest).filter(UploadRequest.folder_id==folder_id).first()
        if req and components(req):raise HTTPException(409,'Declare and upload parts through this submission.')


def aborted_upload(req,version,previous,previous_stored=False):
    """Keep declared membership while detaching a canceled, soft-deleted version."""
    state=deepcopy(req.iteration_state or {})
    for slot_id,item in list(state.get('slots',{}).items()):
        if item.get('version_id')!=str(version.id):continue
        if previous is None:
            state['slots'].pop(slot_id)
        else:
            state['slots'][slot_id]={'asset_id':str(version.asset_id),'version_id':str(previous.id),
                'version_number':previous.version_number,'status':'processing','bytes_stored':previous_stored,
                'findings':[],'attempts':0}
    req.iteration_state=state
