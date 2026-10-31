from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models.entities import AuditLog, Meeting, Task, Project, Participant, now

def utc(value: datetime | None) -> datetime | None:
    if value is None: return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def serialize(obj, exclude: set[str] | None = None) -> dict:
    exclude = exclude or set()
    result = {}
    for column in obj.__table__.columns:
        if column.name in exclude: continue
        value = getattr(obj, column.name)
        if isinstance(value, datetime): value = utc(value).isoformat().replace('+00:00', 'Z')
        result[column.name] = value
    return result

def task_data(task: Task, db: Session) -> dict:
    from models.entities import TaskDependency
    result = serialize(task)
    deadline = utc(task.deadline)
    result['overdue'] = bool(deadline and deadline < now() and task.status != 'completed' and task.approval_status == 'approved')
    result['dependency_ids'] = list(db.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == task.id)))
    return result

def owned(db: Session, model, entity_id: str | None, org_id: str):
    if entity_id is None: return None
    obj = db.get(model, entity_id)
    if not obj or obj.organization_id != org_id: raise HTTPException(404, 'The requested item was not found in this workspace.')
    return obj

def audit(db: Session, org_id: str, user_id: str | None, action: str, entity_type: str = '', entity_id: str = '', details: dict | None = None):
    db.add(AuditLog(organization_id=org_id, user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}))

def notify(db: Session, org_id: str, user_id: str, type: str, title: str, body: str = '', link: str = '/app', key: str | None = None):
    from models.entities import Notification, User
    from services.email import send_email
    from sqlalchemy.exc import IntegrityError
    key = key or f'{type}:{entity_key(link)}:{now().date()}'
    if db.scalar(select(Notification).where(Notification.organization_id == org_id, Notification.user_id == user_id, Notification.dedupe_key == key)): return
    item = Notification(organization_id=org_id, user_id=user_id, type=type, title=title, body=body, link=link, dedupe_key=key)
    db.add(item)
    user = db.get(User, user_id)
    if user and user.email_verified and user.notification_preferences.get('email') and user.notification_preferences.get(type, True) and not user.is_demo:
        send_email(db, user.email, title, body)
    return item

def entity_key(value: str): return value.replace('/', ':')

def validate_dependencies(db: Session, org_id: str, task_id: str | None, dependency_ids: list[str]):
    if len(set(dependency_ids)) != len(dependency_ids): raise HTTPException(422, 'Duplicate dependencies are not allowed.')
    for dep_id in dependency_ids:
        if dep_id == task_id: raise HTTPException(422, 'A task cannot depend on itself.')
        owned(db, Task, dep_id, org_id)
        if task_id and reaches(db, dep_id, task_id, set()): raise HTTPException(422, 'This dependency would create a cycle.')

def reaches(db: Session, start: str, target: str, visited: set[str]) -> bool:
    from models.entities import TaskDependency
    if start == target: return True
    if start in visited: return False
    visited.add(start)
    return any(reaches(db, dep, target, visited) for dep in db.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == start)))
