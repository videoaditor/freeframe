"""Synthetic local browser evidence only. Never connect this harness to production."""
import os
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if 'freeframe_h1' not in os.environ.get('DATABASE_URL',''):
    raise SystemExit('Requires disposable freeframe_h1 database')
os.environ['CORS_ALLOW_ORIGINS']='http://localhost:3181,http://localhost:3182'
from threading import Timer
from apps.api.services import s3_service, review_bridge
s3_service.ensure_bucket_exists = lambda: None
from apps.api.main import app
from apps.api.config import settings
settings.frontend_url='http://localhost:3181'
settings.instance_wide_project_access=True
from apps.api.database import SessionLocal
from apps.api.models.user import User
from apps.api.models.project import Project, ProjectMember, ProjectRole
from apps.api.services.auth_service import hash_password
with SessionLocal() as db:
    user=db.query(User).filter(User.email=='h1@example.com').first()
    if not user:
        user=User(id=uuid.uuid4(),email='h1@example.com',name='Synthetic H1 reviewer',password_hash=hash_password('H1-browser-test'),is_staff=True,is_superadmin=True,email_verified=True)
        db.add(user);db.flush()
        project=Project(id=uuid.uuid4(),name='Synthetic Studio',created_by=user.id,is_workspace=True)
        db.add(project);db.flush();db.add(ProjectMember(project_id=project.id,user_id=user.id,role=ProjectRole.owner));db.commit()
from apps.api.services.checklists import snapshot_digest

def snapshot(intent):
    text=intent.get('brief_text') or 'Show the product. Keep captions readable. Deliver three variants.'
    value={'schema_version':'autoreview.plan-request.v1','tenant_id':intent['tenant_id'],'request_id':intent['binding_id'],'idempotency_key':f"checklist:{intent['tenant_id']}:{intent['binding_id']}",
        'briefing':{'text':text,'version':'fixture','sources':[{'layer':'briefing','reference_id':'synthetic-brief','source_version':'fixture-v1'}]},'rules':[],'brand_context':{'brand':'synthetic','text':'','sources':[]},'limitations':[]}
    return {'snapshot':value,'context_sha256':snapshot_digest(value)}

def plan(snapshot, digest, plan_id=None):
    return {'schema_version':'autoreview.plan.v1','status':'ready','context_sha256':digest,'plan_id':'synthetic-plan-'+snapshot['request_id'],'content_sha256':'a'*64,'version':1,'compiler_version':'synthetic-fixture',
        'requirements':[{'id':'synthetic-product','text':'Keep the product visible during the demonstration.','severity':'warning','applicability':'video','sources':[{'layer':'brand','reference_id':'synthetic-rule','source_version':'fixture-v1'}]},
            {'id':'synthetic-captions','text':'Keep spoken words readable in captions.','severity':'warning','applicability':'video','sources':[{'layer':'basics','reference_id':'synthetic-basics','source_version':'fixture-v1'}]},
            {'id':'synthetic-variants','text':'Deliver all three requested variants.','severity':'warning','applicability':'submission','sources':[{'layer':'briefing','reference_id':'synthetic-brief','source_version':'fixture-v1'}]}], 'limitations':[]}
review_bridge.checklist_card=lambda url:{'card_id':'0123456789abcdef01234567','title':'Synthetic launch'}
review_bridge.checklist_snapshot=snapshot
review_bridge.checklist_plan=plan
review_bridge.register_request=lambda *a,**kw:{'ok':True}
review_bridge.request_status=lambda tokens:{}
review_bridge.asset_stats=lambda *a,**kw:{}
review_bridge.time_saved=lambda *a,**kw:None
from apps.api.routers import requests, checklists, folders
from apps.api.tasks.checklist_tasks import prepare_checklist

def dispatch(binding_id):
    timer=Timer(6,lambda:prepare_checklist.run(str(binding_id)));timer.daemon=True;timer.start()
requests.dispatch_binding=dispatch
checklists.dispatch_binding=dispatch
from apps.api.services import checklists as service
service.dispatch_binding=dispatch
@app.post('/api/gate/card')
def synthetic_card():
    return {'name':'Synthetic launch','brand':'Synthetic Studio','hasBriefing':True,'trelloCardId':'0123456789abcdef01234567'}

import uvicorn
uvicorn.run(app,host='127.0.0.1',port=8017)
