from datetime import timedelta
from fastapi import APIRouter, Request, Response, HTTPException
from sqlalchemy import select
from core.security import Workspace, DB, rate_limit
from models.entities import *
from schemas.contracts import MemoryQuery
from services.common import serialize, task_data, owned, utc
from agents.memory import answer_memory

router = APIRouter(prefix='/api', tags=['memory and reports'])

@router.post('/memory/query')
def query_memory(body: MemoryQuery, request: Request, workspace: Workspace, db: DB):
    user, org, _ = workspace
    rate_limit(request, 'memory', 40, 60)
    owned(db, Project, body.project_id, org.id)
    return answer_memory(db, org.id, body.question, body.project_id)

@router.get('/memory/graph')
def memory_graph(workspace: Workspace, db: DB):
    _, org, _ = workspace
    projects = list(db.scalars(select(Project).where(Project.organization_id == org.id)))
    meetings = list(db.scalars(select(Meeting).where(Meeting.organization_id == org.id).order_by(Meeting.occurred_at.desc()).limit(30)))
    tasks = list(db.scalars(select(Task).where(Task.organization_id == org.id).order_by(Task.created_at.desc()).limit(60)))
    nodes = [{'id': p.id, 'label': p.name, 'type': 'project', 'color': p.color} for p in projects]
    edges = []
    for meeting in meetings:
        nodes.append({'id': meeting.id, 'label': meeting.title, 'type': 'meeting', 'date': utc(meeting.occurred_at).isoformat()})
        if meeting.project_id: edges.append({'source': meeting.project_id, 'target': meeting.id})
    for task in tasks:
        nodes.append({'id': task.id, 'label': task.title, 'type': 'task', 'status': 'overdue' if task_data(task, db)['overdue'] else task.status})
        if task.meeting_id and any(m.id == task.meeting_id for m in meetings): edges.append({'source': task.meeting_id, 'target': task.id})
    return {'nodes': nodes, 'edges': edges, 'mode': 'Source-linked organizational memory', 'counts': {'meetings': len(meetings), 'projects': len(projects), 'commitments': len(tasks)}}

@router.get('/reports')
def reports(workspace: Workspace, db: DB):
    _, org, _ = workspace
    tasks = [task_data(task, db) for task in db.scalars(select(Task).where(Task.organization_id == org.id, Task.approval_status == 'approved'))]
    meetings = list(db.scalars(select(Meeting).where(Meeting.organization_id == org.id)))
    completed = [task for task in tasks if task['status'] == 'completed']
    week = now()-timedelta(days=7)
    completed_week = [task for task in completed if task['completed_at'] and task['completed_at'] >= week.isoformat().replace('+00:00','Z')]
    overdue = [task for task in tasks if task['overdue']]
    return {'generated_at': now().isoformat(), 'title': 'The execution briefing', 'summary': f'{len(meetings)} conversations have produced {len(tasks)} approved commitments. {len(completed)} are complete, {len(tasks)-len(completed)} remain open, and {len(overdue)} need attention.', 'completed_this_week': len(completed_week), 'execution_score': round(len(completed)/len(tasks)*100) if tasks else 0, 'open_tasks': [task for task in tasks if task['status'] != 'completed'], 'completed_tasks': completed, 'overdue_tasks': overdue, 'meetings': [serialize(m) for m in meetings], 'method': 'Calculated from workspace records, not a generated estimate.'}

@router.get('/audit')
def audit_log(workspace: Workspace, db: DB):
    _, org, _ = workspace
    return [serialize(item) for item in db.scalars(select(AuditLog).where(AuditLog.organization_id == org.id).order_by(AuditLog.created_at.desc()).limit(100))]

@router.get('/public/cards/{token}')
def public_card(token: str, response: Response, db: DB):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    meeting = db.scalar(select(Meeting).where(Meeting.share_token == token, Meeting.share_enabled == True))
    if not meeting: raise HTTPException(404, 'This summary is private or the link has been revoked.')
    from api.meetings import card_data
    return card_data(db, meeting)
