-- +goose Up
-- +goose StatementBegin
CREATE TABLE IF NOT EXISTS workflow_instances (
    workflow_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    workflow_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','running','completed','failed','paused','stopped','scheduled')),
    current_step_index INTEGER NOT NULL DEFAULT 0,
    steps JSONB NOT NULL,
    step_results JSONB NOT NULL DEFAULT '[]'::jsonb,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    log_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS step_results (
    id SERIAL PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflow_instances(workflow_id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,
    output JSONB,
    composed_prompt TEXT,
    error TEXT,
    duration_seconds REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS schedules (
    schedule_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    cron TEXT NOT NULL,
    initial_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    role_override TEXT,
    trigger TEXT NOT NULL DEFAULT 'scheduled',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    next_fire_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_events (
    event_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workflow_instances_status ON workflow_instances(status);
CREATE INDEX IF NOT EXISTS idx_step_results_workflow_id ON step_results(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_events_workflow_id ON workflow_events(workflow_id);
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
DROP TABLE IF EXISTS workflow_events;
DROP TABLE IF EXISTS step_results;
DROP TABLE IF EXISTS schedules;
DROP TABLE IF EXISTS workflow_instances;
-- +goose StatementEnd
