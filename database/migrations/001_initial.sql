-- MOMENTUM initial PostgreSQL schema. Apply with database/migrate.py.
CREATE EXTENSION IF NOT EXISTS vector;


CREATE TABLE email_outbox (
	id VARCHAR(36) NOT NULL,
	recipient VARCHAR(320) NOT NULL,
	subject VARCHAR(240) NOT NULL,
	body TEXT NOT NULL,
	status VARCHAR(24) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id VARCHAR(36) NOT NULL,
	email VARCHAR(320) NOT NULL,
	name VARCHAR(120) NOT NULL,
	password_hash VARCHAR(512),
	email_verified BOOLEAN NOT NULL,
	is_demo BOOLEAN NOT NULL,
	onboarded BOOLEAN NOT NULL,
	theme VARCHAR(16) NOT NULL,
	motion VARCHAR(16) NOT NULL,
	notification_preferences JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE organizations (
	id VARCHAR(36) NOT NULL,
	name VARCHAR(120) NOT NULL,
	is_demo BOOLEAN NOT NULL,
	retention_days INTEGER NOT NULL,
	created_by VARCHAR(36),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE verification_tokens (
	id VARCHAR(64) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	kind VARCHAR(24) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	used BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE audit_logs (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36),
	action VARCHAR(100) NOT NULL,
	entity_type VARCHAR(40) NOT NULL,
	entity_id VARCHAR(36) NOT NULL,
	details JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_logs_organization_id ON audit_logs (organization_id);

CREATE TABLE integrations (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	provider VARCHAR(40) NOT NULL,
	status VARCHAR(24) NOT NULL,
	account_label VARCHAR(240) NOT NULL,
	scopes JSON NOT NULL,
	token_encrypted TEXT NOT NULL,
	refresh_encrypted TEXT NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE,
	config JSON NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, provider),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE INDEX ix_integrations_organization_id ON integrations (organization_id);

CREATE TABLE memberships (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	role VARCHAR(16) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, user_id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_memberships_organization_id ON memberships (organization_id);

CREATE INDEX ix_memberships_user_id ON memberships (user_id);

CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	type VARCHAR(32) NOT NULL,
	title VARCHAR(240) NOT NULL,
	body TEXT NOT NULL,
	link VARCHAR(255) NOT NULL,
	read BOOLEAN NOT NULL,
	dedupe_key VARCHAR(255) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, user_id, dedupe_key),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_organization_id ON notifications (organization_id);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE oauth_states (
	id VARCHAR(64) NOT NULL,
	organization_id VARCHAR(36),
	user_id VARCHAR(36),
	provider VARCHAR(40) NOT NULL,
	code_verifier VARCHAR(255) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE participants (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	name VARCHAR(120) NOT NULL,
	email VARCHAR(320),
	role VARCHAR(120) NOT NULL,
	color VARCHAR(16) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE INDEX ix_participants_organization_id ON participants (organization_id);

CREATE TABLE projects (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	name VARCHAR(120) NOT NULL,
	description TEXT NOT NULL,
	color VARCHAR(16) NOT NULL,
	status VARCHAR(24) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE INDEX ix_projects_organization_id ON projects (organization_id);

CREATE TABLE sessions (
	id VARCHAR(64) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36),
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE INDEX ix_sessions_user_id ON sessions (user_id);

CREATE TABLE meetings (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	project_id VARCHAR(36),
	title VARCHAR(200) NOT NULL,
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
	duration_minutes INTEGER NOT NULL,
	status VARCHAR(32) NOT NULL,
	source VARCHAR(24) NOT NULL,
	summary TEXT NOT NULL,
	topics JSON NOT NULL,
	questions JSON NOT NULL,
	risks JSON NOT NULL,
	next_steps JSON NOT NULL,
	provider VARCHAR(64) NOT NULL,
	processing_error TEXT NOT NULL,
	consent BOOLEAN NOT NULL,
	filename VARCHAR(255) NOT NULL,
	storage_key VARCHAR(255) NOT NULL,
	content_type VARCHAR(100) NOT NULL,
	file_size INTEGER NOT NULL,
	created_by VARCHAR(36),
	share_token VARCHAR(64),
	share_enabled BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL,
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL,
	UNIQUE (share_token)
);

CREATE INDEX ix_meetings_project_id ON meetings (project_id);

CREATE INDEX ix_meetings_organization_id ON meetings (organization_id);

CREATE INDEX ix_meetings_status ON meetings (status);

CREATE TABLE decisions (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	meeting_id VARCHAR(36) NOT NULL,
	text TEXT NOT NULL,
	source_segment_ids JSON NOT NULL,
	confidence FLOAT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
);

CREATE INDEX ix_decisions_meeting_id ON decisions (meeting_id);

CREATE INDEX ix_decisions_organization_id ON decisions (organization_id);

CREATE TABLE jobs (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	meeting_id VARCHAR(36),
	kind VARCHAR(32) NOT NULL,
	status VARCHAR(24) NOT NULL,
	attempts INTEGER NOT NULL,
	error TEXT NOT NULL,
	run_after TIMESTAMP WITH TIME ZONE NOT NULL,
	locked_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
);

CREATE INDEX ix_jobs_status ON jobs (status);

CREATE TABLE meeting_participants (
	meeting_id VARCHAR(36) NOT NULL,
	participant_id VARCHAR(36) NOT NULL,
	PRIMARY KEY (meeting_id, participant_id),
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE,
	FOREIGN KEY(participant_id) REFERENCES participants (id) ON DELETE CASCADE
);

CREATE TABLE tasks (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	project_id VARCHAR(36),
	meeting_id VARCHAR(36),
	title VARCHAR(240) NOT NULL,
	description TEXT NOT NULL,
	assignee_id VARCHAR(36),
	deadline TIMESTAMP WITH TIME ZONE,
	priority VARCHAR(16) NOT NULL,
	status VARCHAR(24) NOT NULL,
	source_segment_ids JSON NOT NULL,
	confidence FLOAT NOT NULL,
	approval_status VARCHAR(24) NOT NULL,
	created_by VARCHAR(36),
	completed_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL,
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE SET NULL,
	FOREIGN KEY(assignee_id) REFERENCES participants (id) ON DELETE SET NULL,
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_tasks_deadline ON tasks (deadline);

CREATE INDEX ix_tasks_organization_id ON tasks (organization_id);

CREATE INDEX ix_tasks_assignee_id ON tasks (assignee_id);

CREATE INDEX ix_tasks_meeting_id ON tasks (meeting_id);

CREATE INDEX ix_tasks_status ON tasks (status);

CREATE INDEX ix_tasks_project_id ON tasks (project_id);

CREATE TABLE transcript_segments (
	id VARCHAR(36) NOT NULL,
	meeting_id VARCHAR(36) NOT NULL,
	sequence INTEGER NOT NULL,
	speaker VARCHAR(120) NOT NULL,
	start_seconds FLOAT,
	end_seconds FLOAT,
	text TEXT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
);

CREATE INDEX ix_transcript_segments_meeting_id ON transcript_segments (meeting_id);

CREATE TABLE execution_actions (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	meeting_id VARCHAR(36),
	task_id VARCHAR(36),
	kind VARCHAR(40) NOT NULL,
	status VARCHAR(24) NOT NULL,
	payload JSON NOT NULL,
	source_context TEXT NOT NULL,
	external_id VARCHAR(255),
	result JSON NOT NULL,
	error TEXT NOT NULL,
	approved_by VARCHAR(36),
	approved_at TIMESTAMP WITH TIME ZONE,
	idempotency_key VARCHAR(100) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, idempotency_key),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE SET NULL,
	FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE SET NULL,
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_execution_actions_status ON execution_actions (status);

CREATE INDEX ix_execution_actions_organization_id ON execution_actions (organization_id);

CREATE TABLE memories (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	project_id VARCHAR(36),
	meeting_id VARCHAR(36),
	task_id VARCHAR(36),
	kind VARCHAR(24) NOT NULL,
	content TEXT NOT NULL,
	source_label VARCHAR(240) NOT NULL,
	embedding VECTOR(1536),
	embedding_provider VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL,
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE,
	FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE CASCADE
);

CREATE INDEX ix_memories_meeting_id ON memories (meeting_id);

CREATE INDEX ix_memories_organization_id ON memories (organization_id);

CREATE TABLE task_comments (
	id VARCHAR(36) NOT NULL,
	organization_id VARCHAR(36) NOT NULL,
	task_id VARCHAR(36) NOT NULL,
	author_id VARCHAR(36),
	text TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE CASCADE,
	FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_task_comments_task_id ON task_comments (task_id);

CREATE TABLE task_dependencies (
	task_id VARCHAR(36) NOT NULL,
	depends_on_id VARCHAR(36) NOT NULL,
	PRIMARY KEY (task_id, depends_on_id),
	FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE CASCADE,
	FOREIGN KEY(depends_on_id) REFERENCES tasks (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS memories_embedding_hnsw ON memories USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
