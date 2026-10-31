from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator
from pgvector.sqlalchemy import Vector

def uid() -> str: return str(uuid4())
def now() -> datetime: return datetime.now(timezone.utc)

class Base(DeclarativeBase): pass

class VectorType(TypeDecorator):
    impl = JSON
    cache_ok = True
    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(Vector(1536) if dialect.name == 'postgresql' else JSON())
    def process_bind_param(self, value, dialect):
        return value if dialect.name == 'postgresql' or value is None else list(value)
    def process_result_value(self, value, dialect):
        return value if value is None else list(value)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(String(512))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    theme: Mapped[str] = mapped_column(String(16), default='system')
    motion: Mapped[str] = mapped_column(String(16), default='system')
    notification_preferences: Mapped[dict] = mapped_column(JSON, default=lambda: {'deadlines': True, 'overdue': True, 'processing': True, 'weekly': True, 'email': False, 'reminder_days': 2})
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Organization(Base):
    __tablename__ = 'organizations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Membership(Base):
    __tablename__ = 'memberships'
    __table_args__ = (UniqueConstraint('organization_id', 'user_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(16), default='admin')

class Session(Base):
    __tablename__ = 'sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class VerificationToken(Base):
    __tablename__ = 'verification_tokens'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    kind: Mapped[str] = mapped_column(String(24))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default='')
    color: Mapped[str] = mapped_column(String(16), default='#5B7CFF')
    status: Mapped[str] = mapped_column(String(24), default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Participant(Base):
    __tablename__ = 'participants'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(120), default='Contributor')
    color: Mapped[str] = mapped_column(String(16), default='#5B7CFF')

class Meeting(Base):
    __tablename__ = 'meetings'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey('projects.id', ondelete='SET NULL'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default='uploaded', index=True)
    source: Mapped[str] = mapped_column(String(24), default='transcript')
    summary: Mapped[str] = mapped_column(Text, default='')
    topics: Mapped[list] = mapped_column(JSON, default=list)
    questions: Mapped[list] = mapped_column(JSON, default=list)
    risks: Mapped[list] = mapped_column(JSON, default=list)
    next_steps: Mapped[list] = mapped_column(JSON, default=list)
    provider: Mapped[str] = mapped_column(String(64), default='')
    processing_error: Mapped[str] = mapped_column(Text, default='')
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    filename: Mapped[str] = mapped_column(String(255), default='')
    storage_key: Mapped[str] = mapped_column(String(255), default='')
    content_type: Mapped[str] = mapped_column(String(100), default='')
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    share_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class TranscriptSegment(Base):
    __tablename__ = 'transcript_segments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    meeting_id: Mapped[str] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    speaker: Mapped[str] = mapped_column(String(120), default='Unknown speaker')
    start_seconds: Mapped[float | None] = mapped_column(Float)
    end_seconds: Mapped[float | None] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)

class Decision(Base):
    __tablename__ = 'decisions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'), index=True)
    text: Mapped[str] = mapped_column(Text)
    source_segment_ids: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)

class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey('projects.id', ondelete='SET NULL'), index=True)
    meeting_id: Mapped[str | None] = mapped_column(ForeignKey('meetings.id', ondelete='SET NULL'), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default='')
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey('participants.id', ondelete='SET NULL'), index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    priority: Mapped[str] = mapped_column(String(16), default='medium')
    status: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    source_segment_ids: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    approval_status: Mapped[str] = mapped_column(String(24), default='approved')
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class TaskComment(Base):
    __tablename__ = 'task_comments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'))
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id', ondelete='CASCADE'), index=True)
    author_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class TaskDependency(Base):
    __tablename__ = 'task_dependencies'
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id', ondelete='CASCADE'), primary_key=True)
    depends_on_id: Mapped[str] = mapped_column(ForeignKey('tasks.id', ondelete='CASCADE'), primary_key=True)

class ExecutionAction(Base):
    __tablename__ = 'execution_actions'
    __table_args__ = (UniqueConstraint('organization_id', 'idempotency_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    meeting_id: Mapped[str | None] = mapped_column(ForeignKey('meetings.id', ondelete='SET NULL'))
    task_id: Mapped[str | None] = mapped_column(ForeignKey('tasks.id', ondelete='SET NULL'))
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default='proposed', index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    source_context: Mapped[str] = mapped_column(Text, default='')
    external_id: Mapped[str | None] = mapped_column(String(255))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default='')
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(100), default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Memory(Base):
    __tablename__ = 'memories'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey('projects.id', ondelete='SET NULL'))
    meeting_id: Mapped[str | None] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'), index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey('tasks.id', ondelete='CASCADE'))
    kind: Mapped[str] = mapped_column(String(24))
    content: Mapped[str] = mapped_column(Text)
    source_label: Mapped[str] = mapped_column(String(240), default='')
    embedding: Mapped[list | None] = mapped_column(VectorType())
    embedding_provider: Mapped[str] = mapped_column(String(64), default='lexical')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Integration(Base):
    __tablename__ = 'integrations'
    __table_args__ = (UniqueConstraint('organization_id', 'provider'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default='disconnected')
    account_label: Mapped[str] = mapped_column(String(240), default='')
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    token_encrypted: Mapped[str] = mapped_column(Text, default='')
    refresh_encrypted: Mapped[str] = mapped_column(Text, default='')
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class OAuthState(Base):
    __tablename__ = 'oauth_states'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'))
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    provider: Mapped[str] = mapped_column(String(40))
    code_verifier: Mapped[str] = mapped_column(String(255), default='')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'))
    meeting_id: Mapped[str | None] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'))
    kind: Mapped[str] = mapped_column(String(32), default='process_meeting')
    status: Mapped[str] = mapped_column(String(24), default='queued', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default='')
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Notification(Base):
    __tablename__ = 'notifications'
    __table_args__ = (UniqueConstraint('organization_id', 'user_id', 'dedupe_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text, default='')
    link: Mapped[str] = mapped_column(String(255), default='/app')
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(40), default='')
    entity_id: Mapped[str] = mapped_column(String(36), default='')
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class EmailOutbox(Base):
    __tablename__ = 'email_outbox'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default='local_only')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class MeetingParticipant(Base):
    __tablename__ = 'meeting_participants'
    meeting_id: Mapped[str] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id', ondelete='CASCADE'), primary_key=True)
