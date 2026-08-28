-- ============================================================
-- Pulse — Phase 1 Initial Schema
-- Run this in the Supabase SQL Editor (or Neon SQL console).
-- Requires: CREATE EXTENSION IF NOT EXISTS vector; (already done)
-- ============================================================

-- Enable vector extension (idempotent)
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────
-- events
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    current_phase VARCHAR(100) NOT NULL DEFAULT 'registration',
    timezone VARCHAR(100) NOT NULL DEFAULT 'UTC',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- tracks
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    eligibility_rules TEXT,
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- teams
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    track_id UUID REFERENCES tracks(id) ON DELETE SET NULL,
    repo_url VARCHAR(500),
    readme_ok BOOLEAN NOT NULL DEFAULT FALSE,
    demo_url VARCHAR(500),
    submission_status VARCHAR(50) NOT NULL DEFAULT 'not_submitted',
    readiness_pct FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- participants
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    token_hash VARCHAR(255),
    skills TEXT[] NOT NULL DEFAULT '{}',
    track_pref VARCHAR(100),
    discord_handle VARCHAR(100),
    role VARCHAR(50) NOT NULL DEFAULT 'participant',
    team_id UUID REFERENCES teams(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- schedule_events
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schedule_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    track_scope VARCHAR(255),
    audience_filter VARCHAR(255),
    event_id UUID REFERENCES events(id) ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- documents
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL DEFAULT 'rules',
    ingested_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- rules  (pgvector column)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    text_chunk TEXT NOT NULL,
    embedding vector(384),   -- all-MiniLM-L6-v2 output dimension
    chunk_index INTEGER NOT NULL DEFAULT 0,
    tags VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS rules_embedding_idx
    ON rules USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ─────────────────────────────────────────────
-- mentors
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mentors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    skills TEXT[] NOT NULL DEFAULT '{}',
    availability_status VARCHAR(50) NOT NULL DEFAULT 'available',
    discord_handle VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- submissions  (1:1 with team)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL UNIQUE REFERENCES teams(id) ON DELETE CASCADE,
    repo_url VARCHAR(500),
    readme_url VARCHAR(500),
    demo_url VARCHAR(500),
    description TEXT,
    completeness_pct FLOAT NOT NULL DEFAULT 0.0,
    last_audited_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- submission_requirements
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS submission_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    required BOOLEAN NOT NULL DEFAULT TRUE
);

-- ─────────────────────────────────────────────
-- issues
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id UUID REFERENCES participants(id) ON DELETE SET NULL,
    team_id UUID REFERENCES teams(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    category VARCHAR(100) NOT NULL DEFAULT 'general',
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    urgency_score FLOAT NOT NULL DEFAULT 0.0,
    is_blocking BOOLEAN NOT NULL DEFAULT FALSE,
    severity FLOAT NOT NULL DEFAULT 0.5,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_escalated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- notifications
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id UUID NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL DEFAULT 'in_app',
    content TEXT NOT NULL,
    trigger_reason TEXT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- escalations  (1:1 with issue)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS escalations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID NOT NULL UNIQUE REFERENCES issues(id) ON DELETE CASCADE,
    urgency_score FLOAT NOT NULL DEFAULT 0.0,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    assigned_organizer VARCHAR(255),
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- ─────────────────────────────────────────────
-- mentor_allocations
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mentor_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mentor_id UUID NOT NULL REFERENCES mentors(id) ON DELETE CASCADE,
    issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'proposed',
    reasoning TEXT,
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ
);

-- ─────────────────────────────────────────────
-- resource_items
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resource_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    total_quantity INTEGER NOT NULL DEFAULT 0,
    available_quantity INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- resource_allocations
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resource_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_item_id UUID NOT NULL REFERENCES resource_items(id) ON DELETE CASCADE,
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'allocated',
    allocated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    returned_at TIMESTAMPTZ
);

-- ─────────────────────────────────────────────
-- agent_actions  (explainability log)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type VARCHAR(100) NOT NULL,
    trigger_state_snapshot TEXT,
    reasoning_trace TEXT,
    policy_check_result VARCHAR(100),
    outcome TEXT,
    issue_id UUID REFERENCES issues(id) ON DELETE SET NULL,
    notification_id UUID REFERENCES notifications(id) ON DELETE SET NULL,
    submission_id UUID REFERENCES submissions(id) ON DELETE SET NULL,
    escalation_id UUID REFERENCES escalations(id) ON DELETE SET NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- Alembic version tracking (so alembic upgrade head works later)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
