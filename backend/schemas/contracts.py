from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Signup(Contract):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class Login(Contract):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class EmailRequest(Contract):
    email: EmailStr

class TokenRequest(Contract):
    token: str = Field(min_length=20, max_length=256)

class ResetPassword(TokenRequest):
    password: str = Field(min_length=10, max_length=128)

class Onboarding(Contract):
    name: str = Field(min_length=2, max_length=120)
    account_type: Literal['individual', 'team']
    organization: str = Field(min_length=2, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    team_size: Literal['Just me', '2–10', '11–50', '51–200', '200+']
    use_case: str = Field(min_length=2, max_length=240)
    integrations: list[str] = Field(default_factory=list, max_length=8)
    sample_data: bool = False

class Preferences(Contract):
    theme: Literal['system', 'dark', 'light'] | None = None
    motion: Literal['system', 'full', 'reduced'] | None = None
    notification_preferences: dict | None = None
    @field_validator('notification_preferences')
    @classmethod
    def validate_notifications(cls, value):
        if value is None: return value
        allowed = {'deadlines', 'overdue', 'processing', 'weekly', 'email', 'reminder_days'}
        if set(value) - allowed: raise ValueError('Unknown notification preference')
        for key in allowed - {'reminder_days'}:
            if key in value and not isinstance(value[key], bool): raise ValueError(f'{key} must be a boolean')
        if 'reminder_days' in value and (not isinstance(value['reminder_days'], int) or not 0 <= value['reminder_days'] <= 14): raise ValueError('Reminder days must be between 0 and 14')
        return value

class ProjectInput(Contract):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=2000)
    color: str = Field(default='#5B7CFF', pattern=r'^#[0-9a-fA-F]{6}$')
    status: Literal['active', 'on_hold', 'completed'] = 'active'

class ParticipantInput(Contract):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None
    role: str = Field(default='Contributor', max_length=120)
    color: str = Field(default='#5B7CFF', pattern=r'^#[0-9a-fA-F]{6}$')

class SegmentInput(Contract):
    speaker: str = Field(default='Unknown speaker', max_length=120)
    text: str = Field(min_length=1, max_length=20000)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)

class MeetingInput(Contract):
    title: str = Field(min_length=2, max_length=200)
    occurred_at: datetime | None = None
    project_id: str | None = None
    participants: list[str] = Field(default_factory=list, max_length=100)
    consent: bool
    transcript: str = Field(default='', max_length=500000)
    segments: list[SegmentInput] = Field(default_factory=list, max_length=5000)
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    @field_validator('consent')
    @classmethod
    def consent_required(cls, value):
        if not value: raise ValueError('Confirm that participants consented to recording or processing.')
        return value

class MeetingEdit(Contract):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    summary: str | None = Field(default=None, max_length=20000)
    project_id: str | None = None
    questions: list[str] | None = None
    risks: list[str] | None = None
    next_steps: list[str] | None = None

class DecisionInput(Contract):
    text: str = Field(min_length=1, max_length=4000)
    source_segment_ids: list[str] = Field(default_factory=list)

class TaskInput(Contract):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default='', max_length=10000)
    assignee_id: str | None = None
    deadline: datetime | None = None
    priority: Literal['low', 'medium', 'high', 'urgent'] = 'medium'
    status: Literal['pending', 'in_progress', 'blocked', 'completed'] = 'pending'
    project_id: str | None = None
    meeting_id: str | None = None
    dependency_ids: list[str] = Field(default_factory=list, max_length=50)
    approval_status: Literal['pending', 'approved', 'rejected'] = 'approved'

class TaskEdit(Contract):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    assignee_id: str | None = None
    deadline: datetime | None = None
    priority: Literal['low', 'medium', 'high', 'urgent'] | None = None
    status: Literal['pending', 'in_progress', 'blocked', 'completed'] | None = None
    project_id: str | None = None
    dependency_ids: list[str] | None = Field(default=None, max_length=50)
    approval_status: Literal['pending', 'approved', 'rejected'] | None = None

class CommentInput(Contract):
    text: str = Field(min_length=1, max_length=10000)

class ActionInput(Contract):
    kind: Literal['local_task', 'gmail_draft', 'calendar_event', 'linear_issue', 'notion_page', 'slack_message']
    task_id: str | None = None
    meeting_id: str | None = None
    payload: dict = Field(default_factory=dict)
    source_context: str = Field(default='', max_length=10000)
    idempotency_key: str = Field(default='', max_length=100)

class ActionReview(Contract):
    status: Literal['reviewed', 'approved', 'rejected']
    payload: dict | None = None

class MemoryQuery(Contract):
    question: str = Field(min_length=3, max_length=2000)
    project_id: str | None = None

class ShareInput(Contract):
    enabled: bool
    theme: Literal['dark', 'light', 'blue'] = 'dark'

class RetentionInput(Contract):
    retention_days: int = Field(ge=1, le=3650)

class ExtractedTask(Contract):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default='', max_length=10000)
    assignee: str | None = None
    deadline: str | None = None
    priority: Literal['low', 'medium', 'high', 'urgent'] = 'medium'
    dependencies: list[str] = Field(default_factory=list)
    source_segment_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

class MeetingIntelligence(Contract):
    summary: str = Field(min_length=1, max_length=20000)
    topics: list[str] = Field(default_factory=list, max_length=20)
    decisions: list[DecisionInput] = Field(default_factory=list, max_length=100)
    questions: list[str] = Field(default_factory=list, max_length=100)
    risks: list[str] = Field(default_factory=list, max_length=100)
    next_steps: list[str] = Field(default_factory=list, max_length=100)
    tasks: list[ExtractedTask] = Field(default_factory=list, max_length=200)

class EmailDraftPayload(Contract):
    to: EmailStr
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=50000)

class CalendarPayload(Contract):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default='', max_length=10000)
    start: datetime
    end: datetime
    attendees: list[EmailStr] = Field(default_factory=list, max_length=100)

class LinearPayload(Contract):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default='', max_length=20000)
    team_id: str = Field(min_length=1, max_length=100)

class NotionPayload(Contract):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default='', max_length=10000)
    database_id: str = Field(min_length=1, max_length=100)
    title_property: str = Field(default='Name', min_length=1, max_length=100)

class SlackPayload(Contract):
    channel: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=30000)

class LocalTaskPayload(Contract):
    title: str = Field(min_length=1, max_length=240)

class IntegrationConfig(Contract):
    config: dict = Field(default_factory=dict)
