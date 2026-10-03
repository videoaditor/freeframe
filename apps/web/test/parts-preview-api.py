"""Local synthetic Hand-in UI fixtures. Not an integration or timing benchmark.
Run with Python on 8106; point Next dev on 3206 at this API.
"""
import copy, importlib.util, json, time
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse
spec = importlib.util.spec_from_file_location('preview', Path(__file__).with_name('preview-api.py'))
preview = importlib.util.module_from_spec(spec); spec.loader.exec_module(preview)
preview.USER.update(is_staff=True, id='preview-editor')
for project in preview.PROJECTS: project.update(role='editor', created_by='preview-owner')
STATES = {}
def state(token):
    if token not in STATES:
        p = dict(enabled=True, simple=True, mode='components', submitted=False, can_leave=False, editor_done=False, manifest=dict(schema_version=1,summary='',slots=[],recipes=[]), slots=[], outputs=[], state='waiting', delivered=0,total=0)
        if token != 'empty':
            p['manifest']['slots'] = [dict(id='hook1',label='Hook 01 — Morning routine.mp4',role='hook',group='',script=''),dict(id='hook2',label='Hook 02 — Before your first coffee.mp4',role='hook',group='',script=''),dict(id='body1',label='Body — Product story with end card.mp4',role='body',group='',script='')]
            p['slots'] = [dict(slot_id=s['id'],asset_id=s['id'],version_id=s['id']+'v1',version_number=1,status='clear',bytes_stored=True,findings=[],media_url='http://localhost:8106/demo-media/preview.mp4') for s in p['manifest']['slots']]
            p.update(submitted=True,can_leave=True,editor_done=True,state='rendering',total=2)
            if token == 'held':
                p.update(editor_done=False,state='held');p['slots'][1].update(status='held',findings=[dict(id='n1',t=1,body='Keep the product name inside the safe area.',must_fix=True)])
            if token == 'delivered': p.update(state='delivered',delivered=2)
            p['outputs']=[dict(id='ad'+str(i),label='Hook 0'+str(i)+' · Product story',slot_ids=['hook'+str(i),'body1'],status='delivered' if token=='delivered' else 'rendering',findings=[],download_url='http://localhost:8106/demo-media/preview.mp4') for i in (1,2)]
        STATES[token]=p
    return STATES[token]
class Handler(preview.Handler):
    def send_header(self,key,value):
        if key=='Access-Control-Allow-Origin': value='http://localhost:3206'
        if key=='Access-Control-Allow-Methods': value='GET,POST,PATCH,PUT,DELETE,OPTIONS'
        super().send_header(key,value)
    def do_GET(self):
        path=urlparse(self.path).path
        if path.startswith('/r/'):
            token=path.split('/')[2]
            if path.endswith('/iterations'): return self.send(state(token))
            if path.count('/')==2: return self.send(dict(title='October launch · Morning routine',brand='Northline',receive_iterations=True,assets=[],brief_excerpt='Introduce the product in the first three seconds. Keep the end card readable.',review_share_token='preview'))
        return super().do_GET()
    def do_POST(self):
        path=urlparse(self.path).path
        if path=='/handins':
            self.rfile.read(int(self.headers.get('Content-Length',0)))
            return self.send(dict(token='empty',url='http://localhost:3206/r/empty'))
        if path.startswith('/r/'):
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or '{}'); token=path.split('/')[2]; p=state(token)
            if path.endswith('/iterations/parts'):
                for s in body['parts']:
                    if not any(x['id']==s['id'] for x in p['manifest']['slots']): p['manifest']['slots'].append(dict(**s,group='',script=''))
                return self.send(p)
            if path.endswith('/iterations/submit'): p.update(submitted=True,can_leave=True,editor_done=True,state='rendering'); return self.send(p)
            if path.endswith('/submission-mode'): p['mode']=body['mode']; return self.send(p)
            if path.endswith('/initiate'):
                sid=body['slot_id']; p['slots'].append(dict(slot_id=sid,asset_id=sid,version_id=sid+'v1',version_number=1,status='reviewing',findings=[]));return self.send(dict(upload_id=sid,s3_key=sid,asset_id=sid,version_id=sid+'v1',version_number=1))
            if path.endswith('/presign-part'): return self.send(dict(presigned_url='http://localhost:8106/part'))
            if path.endswith('/complete'):
                for s in p['slots']:
                    if s['slot_id']==body['s3_key']: s.update(status='clear',bytes_stored=True,media_url='http://localhost:8106/demo-media/preview.mp4')
                p['total']=max(1,len([s for s in p['manifest']['slots'] if s['role']=='hook']))
                return self.send({})
            return self.send({})
        return super().do_POST()
    def do_DELETE(self):
        path=urlparse(self.path).path; token=path.split('/')[2]; sid=path.split('/')[-1];p=state(token)
        p['manifest']['slots']=[s for s in p['manifest']['slots'] if s['id']!=sid];p['slots']=[s for s in p['slots'] if s['slot_id']!=sid];return self.send(p)
if __name__=='__main__': ThreadingHTTPServer(('127.0.0.1',8106),Handler).serve_forever()
