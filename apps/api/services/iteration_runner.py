"""One durable request step at a time. Browser polling never drives delivery.

Network work happens outside row locks. A lease prevents duplicate workers; source
version comparison prevents a late result from approving an editor's replacement.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import secrets
import tempfile
import time
import uuid

from sqlalchemy import or_

from ..config import settings
from ..models.asset import Asset, AssetStatus, AssetType, AssetVersion, FileType, MediaFile, ProcessingStatus
from ..models.folder import Folder
from ..models.project import Project
from ..models.share import ShareLink, SharePermission
from ..models.upload_request import UploadRequest
from . import iteration_mixer, review_bridge, s3_service
from .iteration_flow import action_current, next_action, batch_ready, current_recipes
from .iteration_manifest import digest, review_result
from .iteration_requests import locked_request, invalidate_outputs

LEASE_SECONDS=360


def claim(db, request_id):
    now=datetime.now(timezone.utc); token=secrets.token_hex(24)
    q=db.query(UploadRequest).filter(UploadRequest.id==request_id,UploadRequest.receive_iterations.is_(True),
        UploadRequest.iteration_mode=='components',UploadRequest.revoked_at.is_(None),
        or_(UploadRequest.expires_at.is_(None),UploadRequest.expires_at>now),
        or_(UploadRequest.iteration_lease_until.is_(None),UploadRequest.iteration_lease_until<now))
    if q.update({'iteration_lease_token':token,'iteration_lease_until':now+timedelta(seconds=LEASE_SECONDS)},synchronize_session=False)!=1:
        db.rollback(); return None
    db.commit()
    return token


def live_project(db, req):
    return (db.query(Project).filter(Project.id==req.project_id,Project.deleted_at.is_(None)).first() is not None
        and db.query(Folder).filter(Folder.id==req.folder_id,Folder.deleted_at.is_(None)).first() is not None)


def transcode_missing(version_id):
    from ..tasks.cleanup_tasks import _known_job_version_ids
    known=_known_job_version_ids()
    return known is not None and str(version_id) not in known


def refresh_sources(db, req, state):
    pending=[]; now=time.time()
    for slot_id,entry in state.get('slots',{}).items():
        asset=db.query(Asset).filter(Asset.id==uuid.UUID(entry['asset_id']),Asset.deleted_at.is_(None)).first()
        version=db.query(AssetVersion).filter(AssetVersion.asset_id==uuid.UUID(entry['asset_id']),
            AssetVersion.deleted_at.is_(None)).order_by(AssetVersion.version_number.desc()).first()
        if not asset or asset.folder_id!=req.folder_id or not version:
            entry.update(status='error',error='This upload is unavailable. Upload a replacement.',attempts=3)
            continue
        if str(version.id)!=entry['version_id']:
            if getattr(req,'iteration_manifest',None):invalidate_outputs(db,req,state,slot_id)
            entry.update(version_id=str(version.id),version_number=version.version_number,
                status='uploading',bytes_stored=False,findings=[],attempts=0,next_attempt_at=0,processing_queued_at=0,error=None)
        status=version.processing_status
        if status==ProcessingStatus.ready or (status==ProcessingStatus.processing and getattr(version,'iteration_review_ready',False) is True):
            if entry.get('status') in ('uploading','processing'):
                entry.update(status='ready',error=None)
        elif status==ProcessingStatus.failed:
            entry.update(status='error',error='This video could not be processed. Upload a replacement.',attempts=3)
        else:
            entry['status']=status.value
            # Recover a committed upload whose process died before sending its transcode task.
            if status==ProcessingStatus.processing and version.created_at.timestamp()<now-600 and entry.get('processing_queued_at',0)<now-600 and transcode_missing(version.id):
                pending.append((entry['asset_id'],entry['version_id']))
                entry['processing_queued_at']=now
    return pending


def identity(req):
    owner=getattr(req,'iteration_owner_id',None)
    if not isinstance(owner,uuid.UUID): raise RuntimeError('The verified project ownership binding is missing.')
    return {'owner_id':f'freeframe:{owner}','brand_id':f'freeframe:{req.project_id}'}


def register(db, req, share_token):
    from ..models.checklist_binding import ChecklistBinding
    binding=db.query(ChecklistBinding).filter(ChecklistBinding.request_id==req.id,
        ChecklistBinding.project_id==req.project_id,ChecklistBinding.folder_id==req.folder_id,
        ChecklistBinding.deleted_at.is_(None)).first()
    if binding is None or not isinstance(binding.context_sha256,str) or not binding.snapshot or binding.review_share_token!=req.review_share_token:
        raise RuntimeError('The saved checklist is not available yet. Your files are saved; retry shortly.')
    ref={'tenant_id':str(binding.project_id),'binding_id':str(binding.id),'context_sha256':binding.context_sha256,
        'plan_id':binding.plan_id,'content_sha256':binding.content_sha256}
    r=review_bridge.register_request(req.review_share_token,req.brand_slug,req.title,
        binding.snapshot['briefing']['text'],receive_iterations=True,checklist=ref)
    if not r or not r.get('ok') or r.get('brief_status')!='ready':
        raise RuntimeError('The briefing is not available yet. Your files are saved; retry its resolution.')
    if share_token!=req.review_share_token:
        r=review_bridge.register_request(share_token,req.brand_slug,req.title,receive_iterations=True,
            brief_source_token=req.review_share_token)
        if not r or not r.get('ok') or r.get('brief_status')!='ready':
            raise RuntimeError('The resolved briefing could not be attached to this output.')
    return r.get('brand') or req.brand_slug


def media_for(db, version_id):
    return db.query(MediaFile).filter(MediaFile.version_id==uuid.UUID(version_id),MediaFile.file_type==FileType.video).first()


def perform(db, req, action):
    """Return an effect; applying it below rechecks both the lease and source versions."""
    state=deepcopy(req.iteration_state or {}); slots=state.get('slots',{})
    manifest=req.iteration_manifest
    if action['kind']=='deliver_batch':
        entries=[state['outputs'][key] for key in action['keys']]
        result=review_bridge.deliver_iterations({
            'share_token':state['delivery']['share_token'],'card_url':state['internal_handin']['card_url'],
            'editor_name':state['internal_handin']['editor_name'],'submitted':True,
            'required_output_count':len(manifest['recipes']),
            'outputs':[{field:entry[field] for field in ('share_token','asset_id','version_id','review_key')} for entry in entries]})
        if result and result.get('review_conflict'):
            return {'status':'error','review_conflict':True,'error':'Final checks changed; the assembled ads are being checked again.'}
        if not result or not (result.get('posted') is True or result.get('reason')=='already-delivered'):
            raise RuntimeError('Automatic card delivery is unavailable. The finished ads are saved.')
        return {'status':'delivered'}
    if action['kind']=='review_part':
        slot=action['slot']; source=slots[slot['id']]
        brand=register(db,req,req.review_share_token)
        context={'summary':manifest['summary'],'brief':req.iteration_brief or '', 'slot_id':slot['id'],'group':slot['group'],
            'recipes':[r for r in manifest['recipes'] if slot['id'] in r['slots']] if state.get('structured') else []}
        key=digest({'request':str(req.id),'slot':slot,'version':source['version_id'],'context':context,'brand':brand,'policy':1,'generation':source.get('review_generation',0)})
        result=review_bridge.review_iteration({'share_token':req.review_share_token,'brand':brand,
            'asset_id':source['asset_id'],'version_id':source['version_id'],'version_number':source['version_number'],
            'role':slot['role'],'script':slot['script'],
            'context':context,'review_key':key,'require_saved_context':True})
        return {**review_result(result,source['version_id'],key),'brief_resolved':True}
    recipe=action['recipe']; key=action['key']; out=state.get('outputs',{}).get(key,{})
    if action['kind']=='render':
        sources=[]; duration=0; by_id={s['id']:s for s in manifest['slots']}
        for slot_id in recipe['slots']:
            source=slots[slot_id]; media=media_for(db,source['version_id'])
            if not media: raise RuntimeError('One of the source videos is unavailable. Upload a replacement.')
            duration+=getattr(media,'duration_seconds',None) or 0
            if duration>600:
                return {'status':'error','permanent':True,'error':'This combination exceeds the 600-second assembly limit. Shorten its parts.'}
            sources.append({'id':source['asset_id'],'version_id':source['version_id'],'role':by_id[slot_id]['role'],
                            'name':by_id[slot_id]['label'], 'url':s3_service.generate_presigned_get_url(media.s3_key_raw,expires_in=3600)})
        job=iteration_mixer.call('POST','/render',{'key':key,**identity(req),'recipe_id':recipe['id'],
            'sources':sources,'aspect_ratio':req.iteration_ratio})
        if not job.get('job_id') or job.get('status') not in ('queued','processing','ready'):
            raise RuntimeError('Assembly could not start. Your approved parts are saved.')
        return {'job_id':job['job_id'],'status':'rendering','next_attempt_at':time.time()+15}
    if action['kind']=='poll_render':
        job=iteration_mixer.call('GET',f"/jobs/{out['job_id']}",identity(req))
        if job.get('status') in ('queued','processing'):
            return {'status':'rendering','next_attempt_at':time.time()+15}
        if job.get('status')!='ready':
            # Resubmit immutable recipe (with fresh presigned URLs) on a later bounded retry.
            return {'status':'error','job_id':None,'error':'Assembly failed. Your source files are saved.'}
        asset_id=uuid.uuid5(req.id,'iteration-asset:'+key); version_id=uuid.uuid5(req.id,'iteration-version:'+key)
        s3_key=f'raw/{req.project_id}/{asset_id}/{version_id}/original.mp4'
        size=0
        with tempfile.TemporaryFile() as file:
            with iteration_mixer.output(out['job_id'],identity(req)) as response:
                for chunk in response.iter_bytes(1024*1024):
                    size+=len(chunk)
                    if size>2*1024*1024*1024: raise RuntimeError('The assembled video exceeds the 2 GB output limit.')
                    file.write(chunk)
            if not size: raise RuntimeError('Assembly returned an empty video.')
            file.seek(0)
            s3_service.get_s3_client().upload_fileobj(file,settings.s3_bucket,s3_key,ExtraArgs={'ContentType':'video/mp4'})
        return {'status':'reviewing','s3_key':s3_key,'size_bytes':size,'import_output':True}
    if action['kind']=='review_output':
        version=db.query(AssetVersion).filter(AssetVersion.id==uuid.UUID(out['version_id']),AssetVersion.deleted_at.is_(None)).first()
        if not version or version.processing_status==ProcessingStatus.failed:
            raise RuntimeError('The assembled video could not be processed.')
        if version.processing_status!=ProcessingStatus.ready:
            return {'status':'reviewing','next_attempt_at':time.time()+20,'requeue_processing':version.created_at.timestamp()<time.time()-600 and transcode_missing(version.id)}
        brand=register(db,req,out['share_token'])
        by_id={s['id']:s for s in manifest['slots']}
        key_review=digest({'output':key,'version':out['version_id'],'generation':out.get('review_generation',0)})
        context=out['review_context']
        result=review_bridge.review_iteration({'share_token':out['share_token'],'brand':brand,
            'asset_id':out['asset_id'],'version_id':out['version_id'],'version_number':1,'role':'full',
            'script':'\n\n'.join(by_id[s]['script'] for s in recipe['slots']),'context':context,'review_key':key_review,'require_saved_context':True})
        effect=review_result(result,out['version_id'],key_review)
        effect['review_key']=key_review
        effect['brief_resolved']=True
        if effect['status']=='clear': effect['status']='delivered'
        return effect
    raise RuntimeError('Unknown iteration step')


def output_context(db, req, recipe, state):
    slots=state.get('slots',{});by_id={s['id']:s for s in req.iteration_manifest['slots']}
    offset=0.0; source_reviews=[]
    for slot_id in recipe['slots']:
        source=slots[slot_id]; media=media_for(db,source['version_id'])
        duration=media.duration_seconds if media else None
        source_reviews.append({'id':slot_id,'role':by_id[slot_id]['role'],'asset_id':source['asset_id'],'version_id':source['version_id'],
            'offset_seconds':offset,'duration_seconds':duration,
            'findings':[f for f in source.get('findings',[]) if len(f.get('body',''))<=1000][:10]})
        offset=offset+duration if offset is not None and duration is not None else None
    context={'recipe':recipe,'parts':[{k:v for k,v in by_id[s].items() if k!='script'} for s in recipe['slots']], 'component_reviews':source_reviews}
    return context


def import_output(db, req, action, effect):
    """The MP4 is durable before its derived Asset exists. The ID is stable across retries."""
    key=action['key']; asset_id=uuid.uuid5(req.id,'iteration-asset:'+key); version_id=uuid.uuid5(req.id,'iteration-version:'+key)
    asset=db.query(Asset).filter(Asset.id==asset_id).first()
    if asset is None:
        asset=Asset(id=asset_id,project_id=req.project_id,folder_id=None,name=action['recipe']['label'],
            description='Assembled ad; final review pending.',asset_type=AssetType.video,status=AssetStatus.in_review,
            created_by=req.created_by,iteration_pending=True,iteration_derived=True)
        version=AssetVersion(id=version_id,asset_id=asset_id,version_number=1,created_by=req.created_by,processing_status=ProcessingStatus.processing)
        db.add(asset);db.add(version)
        db.add(MediaFile(version_id=version_id,file_type=FileType.video,original_filename=asset.name+'.mp4',mime_type='video/mp4',
            file_size_bytes=effect['size_bytes'],s3_key_raw=effect['s3_key']))
        db.flush()
    token=secrets.token_urlsafe(32)
    db.add(ShareLink(asset_id=asset_id,token=token,created_by=req.created_by,title='Assembly review',
        permission=SharePermission.comment,allow_download=True,visibility='public'))
    effect.update(asset_id=str(asset_id),version_id=str(version_id),share_token=token)
    effect.pop('import_output',None)


def apply_effect(db, req, action, effect):
    state=deepcopy(req.iteration_state or {})
    if not action_current(str(req.id),req.iteration_manifest,state,req.iteration_ratio,action): return False
    if action['kind']=='deliver_batch':
        target=state.setdefault('delivery',{})
    elif action['kind']=='review_part':
        target=state['slots'][action['slot_id']]
    else:
        target=state.setdefault('outputs',{}).setdefault(action['key'],{'label':action['recipe']['label']})
        if effect.get('import_output'): import_output(db,req,action,effect)
    effect=dict(effect)
    if effect.pop('brief_resolved',False):
        state['brief_resolved']=True
        state.pop('brief_input',None)
    if action['kind']=='deliver_batch' and effect.get('review_conflict'):
        for key in action['keys']:
            output=state['outputs'][key]
            output.update(status='reviewing',review_generation=output.get('review_generation',0)+1,attempts=0,next_attempt_at=0)
            output.pop('review_key',None)
            asset=db.query(Asset).filter(Asset.id==uuid.UUID(output['asset_id']),Asset.deleted_at.is_(None)).first()
            if asset:asset.iteration_pending=True;asset.folder_id=None;asset.status=AssetStatus.in_review
        target['started']=False
        effect.update(attempts=0,next_attempt_at=0)
    if effect.get('status')=='error':
        attempts=3 if effect.get('permanent') else target.get('attempts',0)+1
        effect.update(attempts=attempts,next_attempt_at=time.time()+min(600,30*2**attempts))
    elif effect.get('status')=='held':
        effect.update(attempts=0,next_attempt_at=time.time()+60,error=None)
    elif effect.get('status') in ('clear','delivered'):
        effect.update(attempts=0,next_attempt_at=0,error=None)
    target.update(effect)
    if effect.get('status')=='delivered' and action['kind']!='deliver_batch':
        asset=db.query(Asset).filter(Asset.id==uuid.UUID(target['asset_id']),Asset.deleted_at.is_(None)).first()
        if not asset: raise RuntimeError('The reviewed output is unavailable.')
        asset.iteration_pending=False; asset.status=AssetStatus.approved
        asset.folder_id=req.folder_id
        asset.description='Automatically assembled and reviewed from approved parts.'
    req.iteration_state=state
    return True


def run_step(db, request_id):
    token=claim(db,request_id)
    if not token: return False
    action=None; processing=[]
    try:
        req=locked_request(db,request_id)
        if not live_project(db,req):
            req.iteration_lease_token=None;req.iteration_lease_until=None;db.commit();return False
        state=deepcopy(req.iteration_state or {});processing.extend(refresh_sources(db,req,state));req.iteration_state=state
        action=next_action(str(req.id),req.iteration_manifest,state,req.iteration_ratio,time.time())
        if action and action['kind']=='deliver_batch':
            delivery=state.setdefault('delivery',{})
            if not delivery.get('share_token'):
                delivery['share_token']=secrets.token_urlsafe(32)
                db.add(ShareLink(folder_id=req.folder_id,token=delivery['share_token'],created_by=req.iteration_owner_id,
                    title='Finished ads',permission=SharePermission.comment,allow_download=True,visibility='public'))
            delivery['started']=True
            req.iteration_state=deepcopy(state)
        if action and action['kind']=='review_output':
            out=state['outputs'][action['key']]
            if 'review_context' not in out:
                out['review_context']=output_context(db,req,action['recipe'],state)
                req.iteration_state=deepcopy(state)  # Freeze before the first call, including timeout retries.
        db.commit()
        if action:
            try: effect=perform(db,req,action)
            except Exception:
                # Provider details can contain signed URLs. Store a safe actionable message.
                effect={'status':'error','error':'This step could not finish. Your files are saved; automatic retry is scheduled.'}
            req=locked_request(db,request_id)
            if req.iteration_lease_token != token: db.rollback();return False
            if req.revoked_at or (req.expires_at and req.expires_at<=datetime.now(timezone.utc)) or not live_project(db,req):
                req.iteration_lease_token=None;req.iteration_lease_until=None;db.commit();return False
            state=deepcopy(req.iteration_state or {});processing.extend(refresh_sources(db,req,state));req.iteration_state=state
            applied=apply_effect(db,req,action,effect)
            if applied and action['kind'] not in ('review_part','deliver_batch'):
                out=(req.iteration_state or {}).get('outputs',{}).get(action['key'],{})
                if out.get('asset_id') and (effect.get('version_id') or effect.get('requeue_processing')):
                    if out.get('processing_queued_at',0) < time.time()-600:
                        updated=deepcopy(req.iteration_state);updated['outputs'][action['key']]['processing_queued_at']=time.time()
                        req.iteration_state=updated;processing.append((out['asset_id'],out['version_id']))
        else: req=locked_request(db,request_id)
        if batch_ready(str(req.id),req.iteration_manifest,req.iteration_state or {},req.iteration_ratio):
            state=req.iteration_state or {}
            if 'internal_handin' not in state or state.get('delivery',{}).get('status')=='delivered':
                req.completed_at=datetime.now(timezone.utc)
                req.completion_versions={s['asset_id']:s['version_id'] for s in state.get('slots',{}).values()}
        if req.iteration_lease_token==token:
            req.iteration_lease_token=None;req.iteration_lease_until=None
        db.commit()
        if processing:
            from ..routers.requests import _trigger_processing
            for asset_id,version_id in set(processing):
                _trigger_processing(uuid.UUID(asset_id),uuid.UUID(version_id))
        return bool(action)
    except Exception:
        db.rollback()
        # Lease expiry recovers crashed or disconnected workers without corrupting newer state.
        raise
