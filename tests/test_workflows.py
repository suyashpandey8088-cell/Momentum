import re
from types import SimpleNamespace
import io
from datetime import datetime, timezone, timedelta
from agents.intelligence import extract_rule_based, normalize_transcript, resolve_deadline
from schemas.contracts import SegmentInput
from models.entities import *
from core.database import SessionLocal
from workers.runner import tick
from services.storage import validate_magic

TRANSCRIPT='Maya Chen: Let us align on the launch.\nRahul Sharma: I will finish the landing page by Friday.\nPriya Kapoor: I will prepare the website copy by Wednesday.\nMaya Chen: We decided to keep the existing navigation.\nMaya Chen: Who will approve enterprise pricing?'

def import_meeting(client, text=TRANSCRIPT, title='Launch sync'):
    response=client.post('/api/meetings',json={'title':title,'transcript':text,'consent':True,'participants':[]})
    assert response.status_code==201,response.text
    meeting=response.json()
    assert tick()
    detail=client.get(f'/api/meetings/{meeting["id"]}').json()
    assert detail['status']=='ready',detail
    return detail

def test_password_session_and_onboarding(account):
    me=account.get('/api/auth/me').json()['user']
    assert me['email_verified'] is False
    assert me['organization']['name']=='Test Studio'
    assert 'password_hash' not in me
    assert account.get('/api/projects').json()==[]
    assert account.post('/api/auth/logout').status_code==200
    assert account.get('/api/auth/me').status_code==401
    assert account.post('/api/auth/login',json={'email':'owner@example.com','password':'wrong-password'}).status_code==401
    assert account.post('/api/auth/login',json={'email':'owner@example.com','password':'a-secure-test-password'}).status_code==200


def test_reset_revokes_sessions_and_is_single_use(client):
    client.post('/api/auth/signup',json={'name':'Reset User','email':'reset@example.com','password':'initial-password-123'})
    result=client.post('/api/auth/forgot-password',json={'email':'reset@example.com'}).json()
    token=re.search(r'token=([\w-]+)',result['development_link']).group(1)
    assert client.post('/api/auth/reset-password',json={'token':token,'password':'replacement-password-123'}).status_code==200
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/reset-password',json={'token':token,'password':'another-password-123'}).status_code==400
    assert client.post('/api/auth/login',json={'email':'reset@example.com','password':'replacement-password-123'}).status_code==200


def test_verification_is_single_use(client):
    result=client.post('/api/auth/signup',json={'name':'Verify User','email':'verify@example.com','password':'initial-password-123'}).json()
    token=re.search(r'token=([\w-]+)',result['development_link']).group(1)
    assert client.post('/api/auth/verify-email',json={'token':token}).status_code==200
    assert client.get('/api/auth/me').json()['user']['email_verified']
    assert client.post('/api/auth/verify-email',json={'token':token}).status_code==400


def test_demo_is_isolated_and_labeled(client):
    first=client.post('/api/auth/demo').json()
    first_me=client.get('/api/auth/me').json()['user']
    assert first_me['is_demo'] and first_me['organization']['is_demo']
    meetings=client.get('/api/meetings').json()
    assert len(meetings)==6
    other=client.__class__(client.app)
    other.headers['X-Momentum-Client']='web'
    other.post('/api/auth/demo')
    assert other.get('/api/auth/me').json()['user']['organization']['id']!=first_me['organization']['id']
    assert other.get(f'/api/meetings/{meetings[0]["id"]}').status_code==404


def test_consent_and_csrf_are_required(account):
    assert account.post('/api/meetings',json={'title':'No consent','transcript':'Maya: We decided to launch.','consent':False}).status_code==422
    assert account.post('/api/projects',json={'name':'Blocked'},headers={'X-Momentum-Client':''}).status_code==403
    assert account.post('/api/projects',json={'name':'Blocked'},headers={'Sec-Fetch-Site':'cross-site'}).status_code==403


def test_extraction_preserves_owners_deadlines_and_sources():
    reference=datetime(2026,10,31,10,tzinfo=timezone.utc)
    segments=[SimpleNamespace(text=s.text,speaker=s.speaker,id=str(i)) for i,s in enumerate(normalize_transcript(TRANSCRIPT))]
    result=extract_rule_based(segments,['Maya Chen','Rahul Sharma','Priya Kapoor'],reference)
    tasks={t.title:t for t in result.tasks}
    landing=next(t for title,t in tasks.items() if 'landing page' in title)
    copy=next(t for title,t in tasks.items() if 'website copy' in title)
    assert landing.assignee=='Rahul Sharma'
    assert landing.deadline.startswith('2026-11-06')
    assert copy.assignee=='Priya Kapoor'
    assert copy.deadline.startswith('2026-11-04')
    assert landing.source_segment_ids==['1']
    assert any('navigation' in d.text for d in result.decisions)
    assert not any('enterprise pricing' in t.title for t in result.tasks)


def test_unknown_owner_and_deadline_are_never_invented():
    segment=SimpleNamespace(speaker='Unknown speaker',text='We need to review the launch plan.',id='source')
    result=extract_rule_based([segment],[],datetime(2026,10,31,tzinfo=timezone.utc))
    assert len(result.tasks)==1
    assert result.tasks[0].assignee is None
    assert result.tasks[0].deadline is None
    assert result.tasks[0].confidence<0.8


def test_processing_creates_reviewable_tasks_and_memory(demo):
    meeting=import_meeting(demo)
    assert meeting['provider'].startswith('Grounded local rules')
    assert len(meeting['tasks'])>=2
    assert all(t['approval_status']=='pending' for t in meeting['tasks'])
    assert all(t['source_segment_ids'] for t in meeting['tasks'])
    answer=demo.post('/api/memory/query',json={'question':'What happened with the website launch and landing page?'}).json()
    assert answer['sources'] and answer['related_tasks']
    assert 'Lexical' in answer['mode']


def test_approval_is_required_and_idempotent(demo):
    meeting=import_meeting(demo)
    task=meeting['tasks'][0]
    action=next(a for a in meeting['actions'] if a['task_id']==task['id'])
    assert demo.post(f'/api/actions/{action["id"]}/execute').status_code==409
    assert demo.patch(f'/api/tasks/{task["id"]}',json={'approval_status':'approved'}).status_code==422
    assert demo.patch(f'/api/actions/{action["id"]}/review',json={'status':'reviewed'}).status_code==200
    assert demo.patch(f'/api/actions/{action["id"]}/review',json={'status':'approved'}).status_code==200
    result=demo.post(f'/api/actions/{action["id"]}/execute').json()
    assert result['status']=='verified'
    again=demo.post(f'/api/actions/{action["id"]}/execute').json()
    assert again['external_id']==result['external_id']
    assert demo.get(f'/api/tasks/{task["id"]}').json()['approval_status']=='approved'


def test_external_execution_is_blocked_in_demo(demo):
    action=next(a for a in demo.get('/api/actions').json() if a['kind']=='gmail_draft')
    assert demo.patch(f'/api/actions/{action["id"]}/review',json={'status':'approved'}).status_code==403
    assert demo.get(f'/api/integrations/gmail/connect').status_code==403
    assert all(i['status']!='connected' for i in demo.get('/api/integrations').json())


def test_task_crud_comments_search_and_dependency_cycles(account):
    project=account.post('/api/projects',json={'name':'Launch'}).json()
    first=account.post('/api/tasks',json={'title':'Write copy','project_id':project['id']}).json()
    second=account.post('/api/tasks',json={'title':'Build page','project_id':project['id'],'dependency_ids':[first['id']]}).json()
    assert account.patch(f'/api/tasks/{first["id"]}',json={'dependency_ids':[second['id']]}).status_code==422
    assert account.patch(f'/api/tasks/{second["id"]}',json={'status':'completed'}).status_code==409
    assert account.post(f'/api/tasks/{second["id"]}/comments',json={'text':'Waiting for approved copy.'}).status_code==201
    assert len(account.get(f'/api/tasks/{second["id"]}').json()['comments'])==1
    assert account.patch(f'/api/tasks/{first["id"]}',json={'status':'completed'}).status_code==200
    assert account.patch(f'/api/tasks/{second["id"]}',json={'status':'completed'}).status_code==200
    assert account.get('/api/tasks?q=copy&status=completed').json()[0]['id']==first['id']
    assert account.delete(f'/api/tasks/{first["id"]}').status_code==200
    assert account.delete(f'/api/tasks/{second["id"]}').status_code==200


def test_upload_without_stt_is_honest_and_private(account):
    response=account.post('/api/meetings/upload',data={'title':'Audio meeting','consent':'true'},files={'file':('meeting.wav',io.BytesIO(b'RIFF'+b'\x00\x00\x00\x00'+b'WAVE'+b'\x00'*32),'audio/wav')})
    assert response.status_code==201,response.text
    meeting=response.json();assert 'storage_key' not in meeting
    assert tick()
    detail=account.get(f'/api/meetings/{meeting["id"]}').json()
    assert detail['status']=='needs_configuration'
    assert 'speech-to-text' in detail['processing_error']
    assert detail['recording_url']
    assert account.get(detail['recording_url']).status_code==200
    assert account.get(f'/api/meetings/{meeting["id"]}/recording?expires=1&signature=fake').status_code==403
    invalid=account.post('/api/meetings/upload',data={'title':'Bad audio','consent':'true'},files={'file':('fake.mp3',b'not an audio file','audio/mpeg')})
    assert invalid.status_code==422


def test_share_requires_opt_in_and_can_be_revoked(demo):
    meeting=demo.get('/api/meetings').json()[0]
    assert demo.get(f'/api/meetings/{meeting["id"]}/card').json()['share_enabled'] is False
    enabled=demo.post(f'/api/meetings/{meeting["id"]}/share',json={'enabled':True,'theme':'dark'}).json()
    public_path='/api/public/cards/'+enabled['url'].split('/')[-1]
    public=demo.get(public_path).json()
    assert public['title']==meeting['title']
    assert 'segments' not in public and 'participants' not in public and 'organization_id' not in public
    demo.post(f'/api/meetings/{meeting["id"]}/share',json={'enabled':False,'theme':'dark'})
    assert demo.get(public_path).status_code==404


def test_magic_validation():
    assert validate_magic(b'RIFF0000WAVE0000','.wav')
    assert validate_magic(b'0000ftypM4A 0000','.m4a')
    assert validate_magic(b'ID3\x04\x00','.mp3')
    assert not validate_magic(b'<html>fake</html>','.mp3')
    assert not validate_magic(b'RIFF0000WAVE0000','.exe')


def test_export_and_workspace_deletion(account):
    account.post('/api/projects',json={'name':'Private project'})
    export=account.get('/api/export').json()
    assert export['projects'][0]['name']=='Private project'
    assert 'password_hash' not in str(export)
    assert account.delete('/api/settings/workspace').status_code==200
    assert account.get('/api/projects').status_code in (401,428)
