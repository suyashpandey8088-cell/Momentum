from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from pydantic import ValidationError
from core.security import Writer, Workspace, DB, rate_limit
from models.entities import *
from schemas.contracts import *
from services.common import *
from integrations.catalog import CATALOG
from integrations.execution import execute_external

router = APIRouter(prefix='/api/actions', tags=['approval-based execution'])
PAYLOADS = {'local_task': LocalTaskPayload, 'gmail_draft': EmailDraftPayload, 'calendar_event': CalendarPayload, 'linear_issue': LinearPayload, 'notion_page': NotionPayload, 'slack_message': SlackPayload}
PROVIDERS = {value['action']: key for key, value in CATALOG.items() if 'action' in value}

def action_data(action: ExecutionAction):
    return serialize(action)

def validate_payload(kind: str, payload: dict) -> dict:
    try: result = PAYLOADS[kind].model_validate(payload)
    except (ValidationError, KeyError): raise HTTPException(422, f'The proposed {kind.replace("_", " ")} is missing valid fields. Review the draft and try again.')
    data = result.model_dump(mode='json')
    if kind == 'calendar_event' and data['end'] <= data['start']: raise HTTPException(422, 'The event must end after it starts.')
    return data

@router.get('')
def list_actions(workspace: Workspace, db: DB, status: str = ''):
    _, org, _ = workspace
    query = select(ExecutionAction).where(ExecutionAction.organization_id == org.id)
    if status: query = query.where(ExecutionAction.status == status)
    return [action_data(action) for action in db.scalars(query.order_by(ExecutionAction.created_at.desc()).limit(200))]

@router.post('', status_code=201)
def propose_action(body: ActionInput, workspace: Writer, db: DB):
    user, org, _ = workspace
    task = owned(db, Task, body.task_id, org.id)
    meeting = owned(db, Meeting, body.meeting_id, org.id)
    key = body.idempotency_key or str(uuid4())
    existing = db.scalar(select(ExecutionAction).where(ExecutionAction.organization_id == org.id, ExecutionAction.idempotency_key == key))
    if existing: return action_data(existing)
    payload = validate_payload(body.kind, body.payload)
    if body.kind == 'local_task' and not task: raise HTTPException(422, 'Select an extracted task to approve into the workspace.')
    action = ExecutionAction(organization_id=org.id, task_id=task.id if task else None, meeting_id=meeting.id if meeting else None, kind=body.kind, payload=payload, source_context=body.source_context, idempotency_key=key)
    db.add(action); db.flush(); audit(db, org.id, user.id, 'Action proposed', 'action', action.id, {'kind': action.kind}); db.commit()
    return action_data(action)

@router.patch('/{action_id}/review')
def review_action(action_id: str, body: ActionReview, workspace: Writer, db: DB):
    user, org, _ = workspace
    action = owned(db, ExecutionAction, action_id, org.id)
    if action.status not in {'proposed', 'reviewed'}: raise HTTPException(409, 'Only a proposed or reviewed action can change review status.')
    if body.payload is not None: action.payload = validate_payload(action.kind, body.payload)
    if body.status == 'approved':
        if not user.email_verified: raise HTTPException(403, 'Verify your email before approving actions.')
        if action.kind != 'local_task':
            if org.is_demo: raise HTTPException(403, 'External execution is disabled in the sample workspace. Create your own workspace and connect an account.')
            integration = db.scalar(select(Integration).where(Integration.organization_id == org.id, Integration.provider == PROVIDERS[action.kind], Integration.status == 'connected'))
            if not integration: raise HTTPException(409, 'Connect the destination integration before approving this action.')
        task = db.get(Task, action.task_id) if action.task_id else None
        if action.kind == 'local_task' and task and task.status != 'pending': raise HTTPException(409, 'This task has already moved forward. Reject this proposal instead.')
        action.approved_by = user.id; action.approved_at = now()
    action.status = body.status
    audit(db, org.id, user.id, f'Action {body.status}', 'action', action.id, {'kind': action.kind}); db.commit()
    return action_data(action)

@router.post('/{action_id}/execute')
def execute_action(action_id: str, request: Request, workspace: Writer, db: DB):
    user, org, _ = workspace
    rate_limit(request, 'execute', 30, 60)
    action = db.scalar(select(ExecutionAction).where(ExecutionAction.id == action_id, ExecutionAction.organization_id == org.id).with_for_update())
    if not action: raise HTTPException(404, 'Action not found.')
    if action.status in {'executed', 'verified'}: return action_data(action)
    if action.status != 'approved' or not action.approved_by or not action.approved_at: raise HTTPException(409, 'Explicit approval is required before execution.')
    if not user.email_verified: raise HTTPException(403, 'Verify your email before executing actions.')
    action.payload = validate_payload(action.kind, action.payload)
    try:
        if action.kind == 'local_task':
            task = owned(db, Task, action.task_id, org.id)
            task.approval_status = 'approved'; task.updated_at = now()
            db.flush()
            verified = db.scalar(select(Task.id).where(Task.id == task.id, Task.organization_id == org.id, Task.approval_status == 'approved'))
            if not verified: raise ValueError('Task verification failed.')
            result = {'id': task.id, 'verified': True, 'message': 'Task approved and saved to your workspace.', 'url': '/app/tasks'}
        else:
            if org.is_demo: raise HTTPException(403, 'External actions are disabled in demo workspaces.')
            integration = db.scalar(select(Integration).where(Integration.organization_id == org.id, Integration.provider == PROVIDERS[action.kind], Integration.status == 'connected'))
            if not integration: raise HTTPException(409, 'The destination is not connected.')
            result = execute_external(db, integration, action.kind, action.payload)
        action.external_id = str(result['id']); action.result = result; action.status = 'verified' if result.get('verified') else 'executed'; action.error = ''
        audit(db, org.id, user.id, 'Action executed and verified' if action.status == 'verified' else 'Action executed', 'action', action.id, {'kind': action.kind, 'external_id': action.external_id})
        db.commit()
    except HTTPException as error:
        db.rollback(); action = db.get(ExecutionAction, action_id)
        action.status = 'failed'; action.error = str(error.detail); db.commit()
        raise
    except Exception:
        db.rollback(); action = db.get(ExecutionAction, action_id)
        action.status = 'failed'; action.error = 'Execution could not be verified. Check the destination before requesting a new approval.'; db.commit()
        raise HTTPException(502, action.error)
    return action_data(action)

@router.post('/{action_id}/retry')
def retry_action(action_id: str, workspace: Writer, db: DB):
    user, org, _ = workspace
    action = owned(db, ExecutionAction, action_id, org.id)
    if action.status != 'failed' or action.external_id: raise HTTPException(409, 'Only an unconfirmed failure without an external ID can return to review.')
    action.status = 'proposed'; action.approved_at = None; action.approved_by = None; action.error = ''
    audit(db, org.id, user.id, 'Action returned for a new approval', 'action', action.id); db.commit()
    return action_data(action)
