"""Local-only synthetic API for owner UI acceptance checks. No production services or secrets.
Run: python3 apps/web/test/preview-api.py (port 8100).
Then NEXT_PUBLIC_API_URL=http://localhost:8100 npm run dev -- --port 3200 in apps/web.
"""
import base64, json, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

USER = dict(id='preview-owner', name='Alex Morgan', email='owner@example.test', is_staff=False, is_superadmin=False, preferences={})
PROJECTS = [dict(id='p1', name='Northline', is_workspace=True, created_at='2026-09-01'), dict(id='p2', name='Sunday Studio', is_workspace=True, created_at='2026-09-01')]
def request(i, title, status, count, editor, brand='Northline'):
    return dict(id=str(i), token=f'tok{i}', review_share_token=f'delivery{i}', url=f'http://localhost:3200/r/tok{i}', title=title, project_id='p2' if brand=='Sunday Studio' else 'p1', folder_id=f'f{i}', project_name=brand, state='live', assets=count, status=status, open_must_fixes=2 if status=='held' else 0, last_uploader_name=editor, created_at='2026-09-28')
REQUESTS = [request(1,'Autumn launch · Three hooks','held',3,'Jamie'), request(2,'Morning ritual · UGC','reviewing',1,'Robin'), request(3,'The everyday collection','clear',4,'Jamie','Sunday Studio'), request(4,'October brand story','clear',0,None)]
EDITORS = [dict(email='robin@example.test',name='Robin',videos=24,rated=24,first_try_rate=.917,avg_versions=1.1,open_must_fixes=0), dict(email='jamie@example.test',name='Jamie',videos=38,rated=38,first_try_rate=.789,avg_versions=1.3,open_must_fixes=2)]
EDITORS += [dict(email='kai@example.test', name='Kai', videos=8, rated=2, first_try_rate=.5, avg_versions=1.5, open_must_fixes=3), dict(email='sam@example.test', name='Sam', videos=1, rated=0, first_try_rate=None, avg_versions=None, open_must_fixes=0)]
LOGOS = {}
LOGO_BYTES = {}
RULES = {'p1': [
    dict(id='r1', name='Give the logo room to breathe', what='Keep clear space around the logo equal to the height of its mark. Use the original artwork, with no stretching, outlines or added effects.\n\nOn the closing card, keep the logo and product name inside the safe area so they stay visible in every placement.', scope='brand', severity='blocker', active=True),
    dict(id='r2', name='Sound like a person', what='Warm, direct and specific. Say what the product does in everyday language. Avoid jargon, inflated promises and superlatives.', scope='brand', severity='warning', active=True),
    dict(id='r3', name='Let the product lead', what='Make the product easy to recognize in the opening three seconds. Keep the background quiet and show the detail that makes this version distinctive.', scope='brand', severity='warning', active=True),
    dict(id='r4', name='Make every claim count', what='Use only approved product claims. Keep supporting qualifiers readable and on screen alongside the claim. Never imply a result the product cannot support.', scope='brand', severity='blocker', active=True),
    dict(id='global1', name='Keep speech clear', what='The voice should be easy to hear above music. Check the full cut for abrupt level changes.', scope='global', severity='warning', active=True),
], 'p2': []}
SUGGESTIONS = {'p1': [dict(id='s1', name='Give the end card two seconds', what='Let the final product shot and call to action settle before the video ends.', source='owner-comment')], 'p2': []}
MODE = 'normal'
COMPLETED = 0
STAMP = '2026-09-28T09:00:00Z'
FIXTURES = Path(__file__).parent / 'fixtures'


def demo_folders(project_id):
    return [dict(id=r['folder_id'], project_id=project_id, parent_id=None, name=r['title'],
                 created_by=USER['id'], created_at=STAMP, updated_at=STAMP,
                 item_count=r['assets'], children=[]) for r in REQUESTS if r['project_id']==project_id]


def demo_assets():
    result = []
    for request in REQUESTS:
        for index in range(1, request['assets'] + 1):
            aid = f"a{request['id']}-{index}"
            vid = f'{aid}-v1'
            media = dict(id=f'{aid}-file', version_id=vid, file_type='video', original_filename=f'Demo cut {index}.mp4',
                         mime_type='video/mp4', file_size_bytes=(FIXTURES / 'preview.mp4').stat().st_size,
                         width=360, height=640, duration_seconds=3, fps=24, created_at=STAMP)
            version = dict(id=vid, asset_id=aid, version_number=1, processing_status='ready',
                           created_by=USER['id'], created_at=STAMP, deleted_at=None, files=[media])
            result.append(dict(id=aid, project_id=request['project_id'], folder_id=request['folder_id'],
                               name=f'Demo cut {index}', description='Local preview test clip — not a customer ad.',
                               asset_type='video', status='approved' if request['status']=='clear' else 'in_review',
                               rating=None, assignee_id=None, due_date=None, keywords=[], created_by=USER['id'],
                               created_at=STAMP, updated_at=STAMP, deleted_at=None, latest_version=version,
                               thumbnail_url='http://localhost:8100/demo-media/preview.jpg'))
    return result


def project_preview_response(path, query):
    parts = path.strip('/').split('/')
    if parts[0] == 'projects' and len(parts) >= 2:
        project = next((p for p in PROJECTS if p['id']==parts[1]), None)
        if not project:
            return None
        folders = demo_folders(project['id'])
        if len(parts)==2:
            return dict(project, description='Local preview workspace', created_by=USER['id'], project_type='team',
                        role='owner', is_public=False, deleted_at=None, created_at=STAMP)
        if parts[2]=='assets':
            return [a for a in demo_assets() if a['project_id']==project['id']
                    and ('folder_id' not in query or a['folder_id']==query['folder_id'][0])]
        if parts[2]=='folder-tree': return folders
        if parts[2]=='folders': return folders if query.get('parent_id',['root'])[0]=='root' else []
        if parts[2]=='trash': return dict(folders=[], assets=[])
        if parts[2]=='share-links': return []
        if parts[2]=='members': return [dict(id='member', project_id=project['id'], user_id=USER['id'], role='owner', deleted_at=None)]
    if parts[0]=='assets' and len(parts)>=2:
        asset = next((a for a in demo_assets() if a['id']==parts[1]), None)
        if not asset: return None
        if len(parts)==2: return asset
        if parts[2]=='versions': return [asset['latest_version']]
        if parts[2]=='comments': return []
        if parts[2]=='metadata': return []
        if parts[2]=='stream': return dict(url='http://localhost:8100/demo-media/preview.mp4', asset_type='video', mime_type='video/mp4')
    if parts[0]=='share' and len(parts)>=2:
        request=next((r for r in REQUESTS if r['review_share_token']==parts[1]),None)
        if not request: return None
        assets=[a for a in demo_assets() if a['folder_id']==request['folder_id']]
        if len(parts)==2: return dict(folder_id=request['folder_id'],folder_name=request['title'],title=request['title'],permission='comment',allow_download=True,visibility='public',show_versions=True)
        if parts[2]=='assets': return dict(assets=[dict(id=a['id'],name=a['name'],asset_type='video',thumbnail_url=a['thumbnail_url'],file_size=a['latest_version']['files'][0]['file_size_bytes'],duration_seconds=3,comment_count=0,version_count=1,created_by_name=USER['name'],created_at=STAMP) for a in assets],subfolders=[],total=len(assets),page=1,per_page=500)
        if parts[2]=='comments': return []
        if parts[2]=='stream' and len(parts)==4 and any(a['id']==parts[3] for a in assets): return dict(url='http://localhost:8100/demo-media/preview.mp4',asset_type='video',mime_type='video/mp4')
    if path=='/users': return [dict(USER, avatar_url=None)]
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def send(self, value, code=200):
        body=json.dumps(value).encode(); self.send_response(code)
        for k,v in {'Content-Type':'application/json','Access-Control-Allow-Origin':'http://localhost:3200','Access-Control-Allow-Headers':'authorization,content-type,x-freeframe-token','Access-Control-Allow-Methods':'GET,POST,PATCH,PUT,OPTIONS','Access-Control-Expose-Headers':'ETag','ETag':'preview-part','Content-Length':str(len(body))}.items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)
    def do_OPTIONS(self): self.send({})
    def do_PATCH(self):
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or '{}'); USER['preferences'].update(body); self.send(USER)
    def do_PUT(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length',0))); p=urlparse(self.path).path
        if p.startswith('/logo-bytes/'):
            LOGO_BYTES[p]=raw; return self.send({})
        if p.endswith('/branding'):
            if MODE=='error': return self.send({'detail':'Could not save logo. Try again.'},503)
            data=json.loads(raw); pid=p.split('/')[2]; LOGOS[pid]='http://localhost:8100/'+data['logo_s3_key']
            return self.send({'logo_url':LOGOS[pid]})
        self.send({})
    def do_POST(self):
        global MODE, COMPLETED
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or '{}'); p=urlparse(self.path).path
        if p=='/test/mode': MODE=body['mode']; return self.send({})
        if p=='/insights/rules/import':
            if MODE=='error': return self.send({'detail':'Could not read this guide. Please try again.'},503)
            pid=body['project_id']; SUGGESTIONS.setdefault(pid,[]).append(dict(id=str(time.time_ns()),name='New brand guidance',what=body.get('text') or 'Imported guide: keep the product and brand name clearly visible.',source='brand-guide'))
            return self.send(dict(drafted=1,found=1))
        if p=='/insights/rules/suggestion':
            if MODE=='error': return self.send({'detail':'Could not save this rule. Please try again.'},503)
            pid=body['project_id']; suggestion=next((s for s in SUGGESTIONS.get(pid,[]) if s['id']==body['suggestion_id']),None)
            if suggestion and body['action']=='accept': RULES.setdefault(pid,[]).append(dict(id=suggestion['id'],name=suggestion['name'],what=suggestion['what'],scope='brand',severity='warning',active=True))
            SUGGESTIONS[pid]=[s for s in SUGGESTIONS.get(pid,[]) if s['id']!=body['suggestion_id']]
            return self.send(dict(ok=True))
        if p.endswith('/branding/logo-upload'):
            key='logo-bytes/'+p.split('/')[2]+'/'+str(time.time_ns())+'.webp'; return self.send(dict(upload_url='http://localhost:8100/'+key,key=key))
        if p in ('/auth/login', '/auth/refresh'):
            claims=base64.urlsafe_b64encode(json.dumps(dict(exp=int(time.time())+3600)).encode()).decode().rstrip('=')
            token=f'e30.{claims}.local-preview-only'
            return self.send(dict(access_token=token,refresh_token=token,user=USER))
        if p=='/requests':
            project=next(p for p in PROJECTS if p['id']==body['project_id'])
            r=request(len(REQUESTS)+1,body['title'],'clear',0,None,project['name']); REQUESTS.insert(0,r); return self.send(r,201)
        if p.endswith('/initiate'): return self.send(dict(upload_id='preview',s3_key='preview',asset_id='preview-asset',version_id='v1',version_number=1))
        if p.endswith('/complete'): COMPLETED=time.time(); return self.send({})
        if p.endswith('/presign-part'): return self.send(dict(presigned_url='http://localhost:8100/part'))
        return self.send({})
    def do_GET(self):
        p=urlparse(self.path).path
        if p in ('/demo-media/preview.mp4', '/demo-media/preview.jpg'):
            raw=(FIXTURES / p.rsplit('/',1)[1]).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type','video/mp4' if p.endswith('.mp4') else 'image/jpeg')
            self.send_header('Access-Control-Allow-Origin','http://localhost:3200')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers(); self.wfile.write(raw); return
        preview=project_preview_response(p,parse_qs(urlparse(self.path).query))
        if preview is not None: return self.send(preview)
        if p.startswith('/logo-bytes/'):
            raw=LOGO_BYTES.get(p,b''); self.send_response(200); self.send_header('Content-Type','image/webp'); self.end_headers(); self.wfile.write(raw); return
        if p.endswith('/branding'):
            return self.send({'detail':'Could not load logo'},503) if MODE=='error' else self.send(dict(logo_url=LOGOS.get(p.split('/')[2])))
        if p=='/requests': return self.send({'detail':'Preview offline test'},503) if MODE=='error' else self.send([] if MODE=='empty' else REQUESTS)
        if p=='/insights/editors': return self.send(dict(editors=[] if MODE=='empty' else EDITORS,reviewed=MODE!='error'))
        if p=='/insights/rules':
            pid=parse_qs(urlparse(self.path).query).get('project_id',['p1'])[0]
            if MODE=='error': return self.send({'detail':'Rules unavailable'},503)
            return self.send(dict(brand='northline' if pid=='p1' else 'sunday',rules=[] if MODE=='empty' else RULES.get(pid,[]),suggestions=[] if MODE=='empty' else SUGGESTIONS.get(pid,[])))
        if p=='/insights/time-saved': return self.send(dict(days=30,videos=62,totalSec=30600,watchSec=7200,typeSec=23400,assumptions=dict(wpm=40,watches=1),perDay=[dict(day=f'2026-09-{i:02}',sec=1020) for i in range(1,31)],perBrand=[dict(brand='northline',sec=30600,videos=62)]))
        if p.startswith('/r/'):
            if p.endswith('/review'):
                done=COMPLETED and time.time()-COMPLETED>3
                comments=[dict(id='note',t=0,body='Keep the end card visible for one more second.',must_fix=False)] if done else []
                return self.send(dict(assets=[dict(asset_id='preview-asset',name='Morning ritual',version=1,processing='ready' if done else 'processing',comments=comments)],gate=dict(status='clear' if done else 'reviewing',open_must_fixes=0),review_share_token='preview'))
            r=next((r for r in REQUESTS if p.endswith(r['token'])),REQUESTS[0]); return self.send(dict(title=r['title'],brand=r['project_name'],logo_url=LOGOS.get(r['project_id']),assets=[dict(id='preview-asset',name='Morning ritual')],brief_excerpt=None,review_share_token='preview',expires_at=None))
        routes={'/setup/status':dict(needs_setup=False),'/auth/me':USER,'/projects':PROJECTS,'/branding':dict(org_name='Autoreview'),'/instance/settings':dict(storage_limit_bytes=0,storage_used_bytes=0),'/insights/rules':dict(brand='northline',rules=[],suggestions=[])}
        if p.startswith('/notifications') or p.startswith('/me/'): return self.send([])
        return self.send(routes[p]) if p in routes else self.send({'detail':'Not available in this local preview'},404)
if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1',8100),Handler).serve_forever()
