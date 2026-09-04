"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-04

Generated from the SQLAlchemy ORM models (app/models/*) — this is the
canonical schema. `alembic upgrade head` is the only supported way to
provision the database.
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension is required by the rules.embedding column
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""CREATE TABLE documents (
	id UUID NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	type VARCHAR(100) NOT NULL, 
	ingested_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE events (
	id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	current_phase VARCHAR(100) NOT NULL, 
	timezone VARCHAR(100) NOT NULL, 
	deadline_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE mentors (
	id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	skills VARCHAR[] NOT NULL, 
	availability_status VARCHAR(50) NOT NULL, 
	discord_handle VARCHAR(100), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE resource_items (
	id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	resource_type VARCHAR(100) NOT NULL, 
	total_quantity INTEGER NOT NULL, 
	available_quantity INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
)""")
    op.execute("""CREATE TABLE rules (
	id UUID NOT NULL, 
	source_doc_id UUID NOT NULL, 
	text_chunk TEXT NOT NULL, 
	embedding VECTOR(384), 
	chunk_index INTEGER NOT NULL, 
	tags VARCHAR(500), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_doc_id) REFERENCES documents (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE schedule_events (
	id UUID NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	start_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	end_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	track_scope VARCHAR(255), 
	audience_filter VARCHAR(255), 
	event_id UUID, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE tracks (
	id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	eligibility_rules TEXT, 
	event_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE submission_requirements (
	id UUID NOT NULL, 
	track_id UUID NOT NULL, 
	field_name VARCHAR(100) NOT NULL, 
	required BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(track_id) REFERENCES tracks (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE teams (
	id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	track_id UUID, 
	repo_url VARCHAR(500), 
	readme_ok BOOLEAN NOT NULL, 
	demo_url VARCHAR(500), 
	submission_status VARCHAR(50) NOT NULL, 
	readiness_pct FLOAT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(track_id) REFERENCES tracks (id) ON DELETE SET NULL
)""")
    op.execute("""CREATE TABLE participants (
	id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	token_hash VARCHAR(255), 
	skills VARCHAR[] NOT NULL, 
	track_pref VARCHAR(100), 
	discord_handle VARCHAR(100), 
	role VARCHAR(50) NOT NULL, 
	team_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE SET NULL
)""")
    op.execute("""CREATE TABLE resource_allocations (
	id UUID NOT NULL, 
	resource_item_id UUID NOT NULL, 
	team_id UUID NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	allocated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	returned_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(resource_item_id) REFERENCES resource_items (id) ON DELETE CASCADE, 
	FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE submissions (
	id UUID NOT NULL, 
	team_id UUID NOT NULL, 
	repo_url VARCHAR(500), 
	readme_url VARCHAR(500), 
	demo_url VARCHAR(500), 
	description TEXT, 
	completeness_pct FLOAT NOT NULL, 
	last_audited_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (team_id), 
	FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE issues (
	id UUID NOT NULL, 
	participant_id UUID, 
	team_id UUID, 
	description TEXT NOT NULL, 
	category VARCHAR(100) NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	urgency_score FLOAT NOT NULL, 
	is_blocking BOOLEAN NOT NULL, 
	severity FLOAT NOT NULL, 
	retry_count INTEGER NOT NULL, 
	last_escalated_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(participant_id) REFERENCES participants (id) ON DELETE SET NULL, 
	FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE SET NULL
)""")
    op.execute("""CREATE TABLE notifications (
	id UUID NOT NULL, 
	recipient_id UUID NOT NULL, 
	team_id UUID, 
	channel VARCHAR(50) NOT NULL, 
	content TEXT NOT NULL, 
	trigger_reason TEXT, 
	reminder_type VARCHAR(100), 
	read BOOLEAN NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipient_id) REFERENCES participants (id) ON DELETE CASCADE, 
	FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE SET NULL
)""")
    op.execute("""CREATE TABLE escalations (
	id UUID NOT NULL, 
	issue_id UUID NOT NULL, 
	urgency_score FLOAT NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	assigned_organizer VARCHAR(255), 
	resolution_notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (issue_id), 
	FOREIGN KEY(issue_id) REFERENCES issues (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE mentor_allocations (
	id UUID NOT NULL, 
	mentor_id UUID NOT NULL, 
	issue_id UUID NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	reasoning TEXT, 
	proposed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	responded_at TIMESTAMP WITH TIME ZONE, 
	timed_out_at TIMESTAMP WITH TIME ZONE, 
	reoffer_count INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(mentor_id) REFERENCES mentors (id) ON DELETE CASCADE, 
	FOREIGN KEY(issue_id) REFERENCES issues (id) ON DELETE CASCADE
)""")
    op.execute("""CREATE TABLE agent_actions (
	id UUID NOT NULL, 
	action_type VARCHAR(100) NOT NULL, 
	trigger_state_snapshot TEXT, 
	reasoning_trace TEXT, 
	policy_check_result VARCHAR(100), 
	outcome TEXT, 
	issue_id UUID, 
	notification_id UUID, 
	submission_id UUID, 
	escalation_id UUID, 
	executed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(issue_id) REFERENCES issues (id) ON DELETE SET NULL, 
	FOREIGN KEY(notification_id) REFERENCES notifications (id) ON DELETE SET NULL, 
	FOREIGN KEY(submission_id) REFERENCES submissions (id) ON DELETE SET NULL, 
	FOREIGN KEY(escalation_id) REFERENCES escalations (id) ON DELETE SET NULL
)""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS 'agent_actions', 'mentor_allocations', 'escalations', 'notifications', 'issues', 'submissions', 'resource_allocations', 'participants', 'teams', 'submission_requirements', 'tracks', 'schedule_events', 'rules', 'resource_items', 'mentors', 'events', 'documents' CASCADE")
