from datetime import timedelta
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from core.security import Workspace, Writer, Admin, DB
from models.entities import *
from models.entities import Session as UserSession
from schemas.contracts import *
from services.common import *
from services.providers import capabilities

router = APIRouter(prefix='/api', tags=['workspace'])

@router.get('/config')
def config(db: DB):
    return {'name': 'MOMENTUM', 'tagline': 'From conversation to completion.', 'capabilities': capabilities()}

@router.get('/overview')
def overview(workspace: Workspace, db: DB):
    user, org, _ = workspace
    tasks = list(db.scalars(select(Task).where(Task.organization_id == org.id)))
    meetings = list(db.scalars(select(Meeting).where(Meeting.organization_id == org.id).order_by(Meeting.occurred_at.desc())))
    active = [task for task in tasks if task.approval_status == 'approved']
    completed = [task for task in active if task.status == 'completed']
    overdue = [task for task in active if task_data(task, db)['overdue']]
    week = now() - timedelta(days=7)
    projects = list(db.scalars(select(Project).where(Project.organization_id == org.id)))
    project_progress = []
    for project in projects:
        project_tasks = [task for task in active if task.project_id == project.id]
        done = sum(task.status == 'completed' for task in project_tasks)
        project_progress.append({**serialize(project), 'total': len(project_tasks), 'completed': done, 'progress': round(done/len(project_tasks)*100) if project_tasks else 0})
    chart = []
    for offset in range(6, -1, -1):
        day = (now()-timedelta(days=offset)).date()
        created_count = sum(utc(task.created_at).date() == day for task in tasks)
        completed_count = sum(task.completed_at is not None and utc(task.completed_at).date() == day for task in completed)
        chart.append({'day': day.strftime('%a'), 'date': day.isoformat(), 'created': created_count, 'completed': completed_count})
    activity = [serialize(item) for item in db.scalars(select(AuditLog).where(AuditLog.organization_id == org.id).order_by(AuditLog.created_at.desc()).limit(8))]
    upcoming = sorted([task for task in active if task.deadline and task.status != 'completed'], key=lambda task: utc(task.deadline))[:6]
    insights = []
    if overdue: insights.append({'title': f'{len(overdue)} commitment{"s" if len(overdue) != 1 else ""} need a new plan', 'body': 'An overdue task is a conversation waiting to happen. Confirm the blocker and agree on a realistic next step.', 'link': '/app/tasks?filter=overdue', 'tone': 'warning'})
    pending_actions = db.scalar(select(func.count(ExecutionAction.id)).where(ExecutionAction.organization_id == org.id, ExecutionAction.status.in_(['proposed', 'reviewed'])))
    if pending_actions: insights.append({'title': 'Your next moves are ready for review', 'body': f'{pending_actions} proposed actions are waiting. Nothing leaves MOMENTUM without your approval.', 'link': '/app/tasks?tab=approvals', 'tone': 'blue'})
    if active and not overdue: insights.append({'title': 'The team is keeping its commitments', 'body': 'No approved tasks are overdue. Keep the loop closed with a quick progress check.', 'link': '/app/reports', 'tone': 'success'})
    return {'metrics': {'total_meetings': len(meetings), 'meetings_this_week': sum(utc(m.occurred_at) >= week for m in meetings), 'action_items': len(tasks), 'completed': len(completed), 'pending': len(active)-len(completed), 'overdue': len(overdue), 'execution_score': round(len(completed)/len(active)*100) if active else 0, 'pending_approvals': pending_actions}, 'recent_meetings': [{**serialize(m), 'task_count': sum(t.meeting_id == m.id for t in tasks), 'decision_count': db.scalar(select(func.count(Decision.id)).where(Decision.organization_id == org.id, Decision.meeting_id == m.id)), 'participant_ids': list(db.scalars(select(MeetingParticipant.participant_id).where(MeetingParticipant.meeting_id == m.id)))} for m in meetings[:5]], 'upcoming': [task_data(task, db) for task in upcoming], 'projects': project_progress, 'chart': chart, 'activity': activity, 'insights': insights}

@router.get('/projects')
def list_projects(workspace: Workspace, db: DB):
    _, org, _ = workspace
    projects = list(db.scalars(select(Project).where(Project.organization_id == org.id).order_by(Project.created_at)))
    result = []
    for project in projects:
        tasks = list(db.scalars(select(Task).where(Task.organization_id == org.id, Task.project_id == project.id, Task.approval_status == 'approved')))
        done = sum(t.status == 'completed' for t in tasks)
        result.append({**serialize(project), 'total': len(tasks), 'completed': done, 'progress': round(done/len(tasks)*100) if tasks else 0, 'meeting_count': db.scalar(select(func.count(Meeting.id)).where(Meeting.organization_id == org.id, Meeting.project_id == project.id))})
    return result

@router.post('/projects', status_code=201)
def create_project(body: ProjectInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    project = Project(organization_id=org.id, **body.model_dump()); db.add(project); db.flush()
    audit(db, org.id, user.id, 'Project created', 'project', project.id, {'name': project.name}); db.commit()
    return serialize(project)

@router.patch('/projects/{project_id}')
def edit_project(project_id: str, body: ProjectInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    project = owned(db, Project, project_id, org.id)
    for key, value in body.model_dump().items(): setattr(project, key, value)
    audit(db, org.id, user.id, 'Project updated', 'project', project.id); db.commit()
    return serialize(project)

@router.get('/participants')
def list_participants(workspace: Workspace, db: DB):
    _, org, _ = workspace
    return [serialize(p) for p in db.scalars(select(Participant).where(Participant.organization_id == org.id).order_by(Participant.name))]

@router.post('/participants', status_code=201)
def create_participant(body: ParticipantInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    if body.email:
        existing = db.scalar(select(Participant).where(Participant.organization_id == org.id, Participant.email == body.email.lower()))
        if existing: return serialize(existing)
    person = Participant(organization_id=org.id, **{**body.model_dump(), 'email': str(body.email).lower() if body.email else None})
    db.add(person); db.flush(); audit(db, org.id, user.id, 'Participant added', 'participant', person.id); db.commit()
    return serialize(person)

@router.get('/tasks')
def list_tasks(workspace: Workspace, db: DB, q: str = Query('', max_length=200), status: str = '', project_id: str = '', sort: str = 'deadline'):
    _, org, _ = workspace
    query = select(Task).where(Task.organization_id == org.id)
    if q: query = query.where(Task.title.ilike(f'%{q}%'))
    if project_id: query = query.where(Task.project_id == project_id)
    tasks = [task_data(task, db) for task in db.scalars(query)]
    if status: tasks = [task for task in tasks if (task['overdue'] if status == 'overdue' else task['status'] == status)]
    priorities = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
    tasks.sort(key=lambda task: priorities[task['priority']] if sort == 'priority' else task['deadline'] or '9999')
    return tasks

def apply_dependencies(db: Session, task: Task, ids: list[str], org_id: str):
    validate_dependencies(db, org_id, task.id, ids)
    db.execute(delete(TaskDependency).where(TaskDependency.task_id == task.id))
    for dep_id in ids: db.add(TaskDependency(task_id=task.id, depends_on_id=dep_id))

def check_dependencies(db: Session, task: Task):
    ids = list(db.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == task.id)))
    unfinished = [db.get(Task, dep_id).title for dep_id in ids if db.get(Task, dep_id).status != 'completed']
    if unfinished: raise HTTPException(409, 'Complete the dependencies first: ' + ', '.join(unfinished))

@router.post('/tasks', status_code=201)
def create_task(body: TaskInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    owned(db, Participant, body.assignee_id, org.id); owned(db, Project, body.project_id, org.id); owned(db, Meeting, body.meeting_id, org.id)
    data = body.model_dump(exclude={'dependency_ids'})
    task = Task(**data, organization_id=org.id, created_by=user.id, completed_at=now() if body.status == 'completed' else None)
    db.add(task); db.flush(); apply_dependencies(db, task, body.dependency_ids, org.id)
    if task.status in ['completed', 'in_progress']: check_dependencies(db, task)
    audit(db, org.id, user.id, 'Task created', 'task', task.id, {'title': task.title}); db.commit()
    return task_data(task, db)

@router.get('/tasks/{task_id}')
def get_task(task_id: str, workspace: Workspace, db: DB):
    _, org, _ = workspace
    task = owned(db, Task, task_id, org.id)
    comments = []
    for comment in db.scalars(select(TaskComment).where(TaskComment.organization_id == org.id, TaskComment.task_id == task.id).order_by(TaskComment.created_at)):
        author = db.get(User, comment.author_id) if comment.author_id else None
        comments.append({**serialize(comment), 'author': author.name if author else 'Former member'})
    return {**task_data(task, db), 'comments': comments}

@router.patch('/tasks/{task_id}')
def edit_task(task_id: str, body: TaskEdit, workspace: Writer, db: DB):
    user, org, _ = workspace
    task = owned(db, Task, task_id, org.id)
    changes = body.model_dump(exclude_unset=True, exclude={'dependency_ids'})
    if 'approval_status' in changes and changes['approval_status'] != task.approval_status: raise HTTPException(422, 'Use the approval queue to approve or reject extracted commitments.')
    owned(db, Participant, changes.get('assignee_id'), org.id); owned(db, Project, changes.get('project_id'), org.id)
    old_status = task.status
    for key, value in changes.items(): setattr(task, key, value)
    if body.dependency_ids is not None: apply_dependencies(db, task, body.dependency_ids, org.id)
    if task.status in ['completed', 'in_progress']: check_dependencies(db, task)
    if task.status == 'completed' and old_status != 'completed': task.completed_at = now()
    if task.status != 'completed': task.completed_at = None
    task.updated_at = now()
    audit(db, org.id, user.id, 'Task completed' if task.status == 'completed' and old_status != 'completed' else 'Task updated', 'task', task.id, {'title': task.title, 'status': task.status}); db.commit()
    return task_data(task, db)

@router.delete('/tasks/{task_id}')
def delete_task(task_id: str, workspace: Writer, db: DB):
    user, org, _ = workspace
    task = owned(db, Task, task_id, org.id)
    if db.scalar(select(TaskDependency.task_id).where(TaskDependency.depends_on_id == task.id, TaskDependency.task_id != task.id)):
        dependents = list(db.scalars(select(Task).join(TaskDependency, TaskDependency.task_id == Task.id).where(TaskDependency.depends_on_id == task.id, Task.status != 'completed')))
        if dependents: raise HTTPException(409, 'Other open tasks depend on this task. Remove those dependencies first.')
    for action in db.scalars(select(ExecutionAction).where(ExecutionAction.organization_id == org.id, ExecutionAction.task_id == task.id, ExecutionAction.status.in_(['proposed', 'reviewed', 'approved']))): action.status = 'rejected'
    audit(db, org.id, user.id, 'Task deleted', 'task', task.id, {'title': task.title}); db.delete(task); db.commit()
    return {'ok': True}

@router.post('/tasks/{task_id}/comments', status_code=201)
def add_comment(task_id: str, body: CommentInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    owned(db, Task, task_id, org.id)
    comment = TaskComment(organization_id=org.id, task_id=task_id, author_id=user.id, text=body.text)
    db.add(comment); db.flush(); audit(db, org.id, user.id, 'Comment added', 'task', task_id); db.commit()
    return {**serialize(comment), 'author': user.name}

@router.get('/notifications')
def notifications(workspace: Workspace, db: DB):
    user, org, _ = workspace
    return [serialize(item) for item in db.scalars(select(Notification).where(Notification.organization_id == org.id, Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50))]

@router.post('/notifications/read')
def read_notifications(workspace: Workspace, db: DB, all: bool = False, notification_id: str | None = None):
    user, org, _ = workspace
    query = select(Notification).where(Notification.organization_id == org.id, Notification.user_id == user.id)
    if not all: query = query.where(Notification.id == notification_id)
    for item in db.scalars(query): item.read = True
    db.commit(); return {'ok': True}

@router.get('/settings')
def workspace_settings(workspace: Workspace, db: DB):
    user, org, membership = workspace
    members = []
    for m in db.scalars(select(Membership).where(Membership.organization_id == org.id)):
        member = db.get(User, m.user_id)
        members.append({'id': member.id, 'name': member.name, 'email': member.email, 'role': m.role})
    return {'organization': serialize(org), 'members': members, 'preferences': user.notification_preferences, 'capabilities': capabilities(), 'role': membership.role}

@router.patch('/settings/retention')
def set_retention(body: RetentionInput, workspace: Admin, db: DB):
    user, org, _ = workspace
    org.retention_days = body.retention_days
    audit(db, org.id, user.id, 'Retention policy updated', 'organization', org.id, {'days': body.retention_days}); db.commit()
    return serialize(org)

@router.get('/export')
def export_workspace(workspace: Admin, db: DB):
    user, org, _ = workspace
    from models import entities
    tables = [Project, Participant, Meeting, TranscriptSegment, Decision, Task, TaskComment, ExecutionAction, Memory, Notification, AuditLog]
    result = {'organization': serialize(org), 'exported_at': now().isoformat(), 'notice': 'Private workspace export. Recording binaries are available separately through signed URLs.'}
    for model in tables:
        query = select(model).where(model.organization_id == org.id) if hasattr(model, 'organization_id') else select(model).join(Meeting).where(Meeting.organization_id == org.id)
        result[model.__tablename__] = [serialize(item) for item in db.scalars(query)]
    audit(db, org.id, user.id, 'Workspace exported'); db.commit()
    return result

@router.delete('/settings/workspace')
def delete_workspace(workspace: Admin, db: DB):
    user, org, _ = workspace
    from services.storage import delete_recording
    for meeting in db.scalars(select(Meeting).where(Meeting.organization_id == org.id)):
        if meeting.storage_key: delete_recording(meeting.storage_key)
    for session in db.scalars(select(UserSession).where(UserSession.organization_id == org.id)): db.delete(session)
    db.flush()
    db.delete(org); db.commit()
    return {'ok': True, 'next': '/onboarding'}
