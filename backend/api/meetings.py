import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select, delete, func
from pydantic import ValidationError
from core.security import Workspace, Writer, DB, rate_limit
from models.entities import *
from schemas.contracts import *
from services.common import *
from services.storage import *
from agents.intelligence import normalize_transcript

router = APIRouter(prefix='/api/meetings', tags=['meetings'])

def meeting_detail(db: Session, meeting: Meeting, org_id: str):
    participants = list(db.scalars(select(Participant).join(MeetingParticipant, MeetingParticipant.participant_id == Participant.id).where(MeetingParticipant.meeting_id == meeting.id)))
    segments = list(db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting.id).order_by(TranscriptSegment.sequence)))
    decisions = list(db.scalars(select(Decision).where(Decision.organization_id == org_id, Decision.meeting_id == meeting.id)))
    tasks = list(db.scalars(select(Task).where(Task.organization_id == org_id, Task.meeting_id == meeting.id)))
    actions = list(db.scalars(select(ExecutionAction).where(ExecutionAction.organization_id == org_id, ExecutionAction.meeting_id == meeting.id)))
    from api.actions import action_data
    return {**serialize(meeting, {'storage_key'}), 'participants': [serialize(p) for p in participants], 'segments': [serialize(s) for s in segments], 'decisions': [serialize(d) for d in decisions], 'tasks': [task_data(t, db) for t in tasks], 'actions': [action_data(a) for a in actions], 'recording_url': signed_recording_url(meeting.id) if meeting.storage_key else None}

def add_segments(db: Session, meeting: Meeting, segments: list[SegmentInput]):
    for sequence, segment in enumerate(segments):
        db.add(TranscriptSegment(meeting_id=meeting.id, sequence=sequence, **segment.model_dump()))

def add_participants(db: Session, meeting: Meeting, ids: list[str], org_id: str):
    for participant_id in set(ids):
        owned(db, Participant, participant_id, org_id)
        db.add(MeetingParticipant(meeting_id=meeting.id, participant_id=participant_id))

@router.get('')
def list_meetings(workspace: Workspace, db: DB, q: str = Query('', max_length=200), project_id: str = '', status: str = ''):
    _, org, _ = workspace
    query = select(Meeting).where(Meeting.organization_id == org.id)
    if q: query = query.where(Meeting.title.ilike(f'%{q}%'))
    if project_id: query = query.where(Meeting.project_id == project_id)
    if status: query = query.where(Meeting.status == status)
    result = []
    for meeting in db.scalars(query.order_by(Meeting.occurred_at.desc()).limit(200)):
        result.append({**serialize(meeting, {'storage_key'}), 'task_count': db.scalar(select(func.count(Task.id)).where(Task.organization_id == org.id, Task.meeting_id == meeting.id)), 'decision_count': db.scalar(select(func.count(Decision.id)).where(Decision.organization_id == org.id, Decision.meeting_id == meeting.id)), 'participant_ids': list(db.scalars(select(MeetingParticipant.participant_id).where(MeetingParticipant.meeting_id == meeting.id)))})
    return result

@router.post('', status_code=201)
def create_meeting(body: MeetingInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    owned(db, Project, body.project_id, org.id)
    if not body.transcript.strip() and not body.segments: raise HTTPException(422, 'Add a transcript or meeting notes to process.')
    segments = body.segments or normalize_transcript(body.transcript)
    if not segments: raise HTTPException(422, 'The transcript contains no readable text.')
    meeting = Meeting(organization_id=org.id, project_id=body.project_id, title=body.title, occurred_at=body.occurred_at or now(), consent=body.consent, duration_minutes=body.duration_minutes, source='transcript', status='queued', created_by=user.id)
    db.add(meeting); db.flush(); add_segments(db, meeting, segments); add_participants(db, meeting, body.participants, org.id)
    db.add(Job(organization_id=org.id, meeting_id=meeting.id)); audit(db, org.id, user.id, 'Meeting imported', 'meeting', meeting.id, {'title': meeting.title}); db.commit()
    return serialize(meeting, {'storage_key'})

@router.post('/upload', status_code=201)
def upload_meeting(request: Request, workspace: Writer, db: DB, file: UploadFile = File(...), title: str = Form(...), consent: bool = Form(...), project_id: str = Form(''), participant_ids: str = Form('[]'), occurred_at: str = Form('')):
    user, org, _ = workspace
    rate_limit(request, 'upload', 20, 3600)
    if not consent: raise HTTPException(422, 'Recording consent must be confirmed.')
    if not 2 <= len(title.strip()) <= 200: raise HTTPException(422, 'Meeting title must be 2–200 characters.')
    owned(db, Project, project_id or None, org.id)
    try: ids = json.loads(participant_ids)
    except json.JSONDecodeError: raise HTTPException(422, 'Participant IDs must be a JSON list.')
    if not isinstance(ids, list) or len(ids) > 100 or not all(isinstance(i, str) for i in ids): raise HTTPException(422, 'Invalid participants.')
    for participant_id in ids: owned(db, Participant, participant_id, org.id)
    occurred = now()
    if occurred_at:
        try: occurred = datetime.fromisoformat(occurred_at.replace('Z', '+00:00'))
        except ValueError: raise HTTPException(422, 'Invalid meeting date.')
    key, filename, size = store_upload(file, org.id)
    try:
        meeting = Meeting(organization_id=org.id, project_id=project_id or None, title=title.strip(), occurred_at=occurred, consent=True, source='upload', status='uploaded', created_by=user.id, storage_key=key, filename=filename, content_type=file.content_type or 'application/octet-stream', file_size=size)
        db.add(meeting); db.flush(); add_participants(db, meeting, ids, org.id)
        db.add(Job(organization_id=org.id, meeting_id=meeting.id)); audit(db, org.id, user.id, 'Recording uploaded', 'meeting', meeting.id, {'size': size}); db.commit()
    except Exception:
        delete_recording(key); raise
    return serialize(meeting, {'storage_key'})

@router.get('/{meeting_id}')
def get_meeting(meeting_id: str, workspace: Workspace, db: DB):
    _, org, _ = workspace
    return meeting_detail(db, owned(db, Meeting, meeting_id, org.id), org.id)

@router.get('/{meeting_id}/recording')
def get_recording(meeting_id: str, workspace: Workspace, db: DB, expires: int, signature: str):
    _, org, _ = workspace
    meeting = owned(db, Meeting, meeting_id, org.id)
    verify_signature(meeting_id, expires, signature)
    from services.object_storage import remote_signed_url
    remote = remote_signed_url(meeting.storage_key)
    if remote: return RedirectResponse(remote)
    return FileResponse(recording_path(meeting.storage_key), filename=meeting.filename, content_disposition_type='inline')

@router.patch('/{meeting_id}')
def edit_meeting(meeting_id: str, body: MeetingEdit, workspace: Writer, db: DB):
    user, org, _ = workspace
    meeting = owned(db, Meeting, meeting_id, org.id)
    changes = body.model_dump(exclude_unset=True)
    if 'project_id' in changes: owned(db, Project, changes['project_id'], org.id)
    for key, value in changes.items(): setattr(meeting, key, value)
    audit(db, org.id, user.id, 'Meeting intelligence edited', 'meeting', meeting.id); db.commit()
    return meeting_detail(db, meeting, org.id)

@router.patch('/{meeting_id}/decisions/{decision_id}')
def edit_decision(meeting_id: str, decision_id: str, body: DecisionInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    owned(db, Meeting, meeting_id, org.id)
    decision = owned(db, Decision, decision_id, org.id)
    if decision.meeting_id != meeting_id: raise HTTPException(404, 'Decision not found.')
    decision.text = body.text
    audit(db, org.id, user.id, 'Decision edited', 'decision', decision.id); db.commit()
    return serialize(decision)

@router.post('/{meeting_id}/decisions', status_code=201)
def create_decision(meeting_id: str, body: DecisionInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    owned(db, Meeting, meeting_id, org.id)
    decision = Decision(organization_id=org.id, meeting_id=meeting_id, **body.model_dump(), confidence=1)
    db.add(decision); db.flush(); audit(db, org.id, user.id, 'Decision added', 'decision', decision.id); db.commit()
    return serialize(decision)

@router.post('/{meeting_id}/reprocess')
def reprocess(meeting_id: str, workspace: Writer, db: DB):
    user, org, _ = workspace
    meeting = owned(db, Meeting, meeting_id, org.id)
    if db.scalar(select(Job).where(Job.meeting_id == meeting.id, Job.status.in_(['queued', 'processing']))): raise HTTPException(409, 'This meeting is already being processed.')
    meeting.status = 'queued'; meeting.processing_error = ''
    db.add(Job(organization_id=org.id, meeting_id=meeting.id)); audit(db, org.id, user.id, 'Meeting reprocessing requested', 'meeting', meeting.id); db.commit()
    return serialize(meeting, {'storage_key'})

@router.delete('/{meeting_id}')
def delete_meeting(meeting_id: str, workspace: Writer, db: DB):
    user, org, _ = workspace
    meeting = owned(db, Meeting, meeting_id, org.id)
    for action in db.scalars(select(ExecutionAction).where(ExecutionAction.organization_id == org.id, ExecutionAction.meeting_id == meeting.id, ExecutionAction.status.in_(['proposed', 'reviewed', 'approved']))): action.status = 'rejected'
    delete_recording(meeting.storage_key)
    audit(db, org.id, user.id, 'Meeting and recording deleted', 'meeting', meeting.id, {'title': meeting.title})
    db.delete(meeting); db.commit()
    return {'ok': True}

@router.post('/{meeting_id}/share')
def set_share(meeting_id: str, body: ShareInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    meeting = owned(db, Meeting, meeting_id, org.id)
    if not user.email_verified: raise HTTPException(403, 'Verify your email before sharing meeting information.')
    if body.enabled and not meeting.share_token:
        from core.security import new_token
        meeting.share_token = new_token()
    meeting.share_enabled = body.enabled
    audit(db, org.id, user.id, 'Public summary sharing enabled' if body.enabled else 'Public summary sharing revoked', 'meeting', meeting.id)
    db.commit()
    return {'enabled': meeting.share_enabled, 'url': f'/share/{meeting.share_token}' if meeting.share_enabled else None, 'theme': body.theme}

@router.get('/{meeting_id}/card')
def private_card(meeting_id: str, workspace: Workspace, db: DB):
    _, org, _ = workspace
    return card_data(db, owned(db, Meeting, meeting_id, org.id))

def card_data(db: Session, meeting: Meeting):
    tasks = list(db.scalars(select(Task).where(Task.organization_id == meeting.organization_id, Task.meeting_id == meeting.id, Task.approval_status == 'approved')))
    completed = sum(task.status == 'completed' for task in tasks)
    decisions = list(db.scalars(select(Decision.text).where(Decision.organization_id == meeting.organization_id, Decision.meeting_id == meeting.id).limit(3)))
    return {'title': meeting.title, 'date': utc(meeting.occurred_at).isoformat(), 'decisions': decisions, 'action_items': len(tasks), 'completed': completed, 'pending': len(tasks)-completed, 'progress': round(completed/len(tasks)*100) if tasks else 0, 'share_enabled': meeting.share_enabled, 'share_url': f'/share/{meeting.share_token}' if meeting.share_enabled else None}
