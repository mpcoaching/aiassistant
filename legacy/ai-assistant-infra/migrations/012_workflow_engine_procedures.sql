-- +goose Up
-- +goose StatementBegin
-- Upsert a workflow instance (insert or update mutable columns on conflict)
CREATE OR REPLACE FUNCTION upsert_workflow_instance(
    p_workflow_id TEXT,
    p_workflow_name TEXT,
    p_workflow_path TEXT,
    p_status TEXT,
    p_current_step_index INTEGER,
    p_steps_json JSONB,
    p_step_results_json JSONB,
    p_context_json JSONB,
    p_error TEXT,
    p_log_path TEXT
) RETURNS VOID AS $$
BEGIN
    INSERT INTO workflow_instances
        (workflow_id, workflow_name, workflow_path, status, current_step_index, steps, step_results, context, error, log_path, updated_at)
    VALUES
        (p_workflow_id, p_workflow_name, p_workflow_path, p_status, p_current_step_index, p_steps_json, p_step_results_json, p_context_json, p_error, p_log_path, now())
    ON CONFLICT (workflow_id) DO UPDATE SET
        status = EXCLUDED.status,
        current_step_index = EXCLUDED.current_step_index,
        step_results = EXCLUDED.step_results,
        context = EXCLUDED.context,
        error = EXCLUDED.error,
        updated_at = EXCLUDED.updated_at;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose StatementBegin
-- Insert a single step result
CREATE OR REPLACE FUNCTION insert_step_result(
    p_workflow_id TEXT,
    p_step_index INTEGER,
    p_step_name TEXT,
    p_step_type TEXT,
    p_status TEXT,
    p_output_json JSONB,
    p_composed_prompt TEXT,
    p_error TEXT,
    p_duration_seconds REAL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO step_results
        (workflow_id, step_index, step_name, step_type, status, output, composed_prompt, error, duration_seconds)
    VALUES
        (p_workflow_id, p_step_index, p_step_name, p_step_type, p_status, p_output_json, p_composed_prompt, p_error, p_duration_seconds);
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose StatementBegin
-- Insert a workflow event, ignoring duplicates by event_id
CREATE OR REPLACE FUNCTION insert_workflow_event(
    p_event_id TEXT,
    p_workflow_id TEXT,
    p_event_type TEXT,
    p_payload_json JSONB
) RETURNS VOID AS $$
BEGIN
    INSERT INTO workflow_events (event_id, workflow_id, event_type, payload)
    VALUES (p_event_id, p_workflow_id, p_event_type, p_payload_json)
    ON CONFLICT (event_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose StatementBegin
-- Return all enabled schedules for the scheduler
CREATE OR REPLACE FUNCTION get_enabled_schedules()
RETURNS TABLE(
    schedule_id TEXT,
    workflow_name TEXT,
    cron TEXT,
    initial_context JSONB,
    role_override TEXT,
    trigger TEXT,
    enabled BOOLEAN,
    next_fire_time TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT s.schedule_id, s.workflow_name, s.cron, s.initial_context, s.role_override, s.trigger, s.enabled, s.next_fire_time
    FROM schedules s
    WHERE s.enabled = TRUE;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose StatementBegin
-- Upsert a schedule (insert or update enabled/next_fire_time on conflict)
CREATE OR REPLACE FUNCTION upsert_schedule(
    p_schedule_id TEXT,
    p_workflow_name TEXT,
    p_cron TEXT,
    p_initial_context_json JSONB,
    p_role_override TEXT,
    p_trigger TEXT,
    p_enabled BOOLEAN,
    p_next_fire_time TIMESTAMPTZ
) RETURNS VOID AS $$
BEGIN
    INSERT INTO schedules
        (schedule_id, workflow_name, cron, initial_context, role_override, trigger, enabled, next_fire_time, updated_at)
    VALUES
        (p_schedule_id, p_workflow_name, p_cron, p_initial_context_json, p_role_override, p_trigger, p_enabled, p_next_fire_time, now())
    ON CONFLICT (schedule_id) DO UPDATE SET
        enabled = EXCLUDED.enabled,
        next_fire_time = EXCLUDED.next_fire_time,
        updated_at = EXCLUDED.updated_at;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose StatementBegin
-- Delete a schedule by id
CREATE OR REPLACE FUNCTION delete_schedule(p_schedule_id TEXT) RETURNS VOID AS $$
BEGIN
    DELETE FROM schedules WHERE schedule_id = p_schedule_id;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose StatementBegin
-- Fetch a single workflow instance by id
CREATE OR REPLACE FUNCTION get_workflow_instance(p_workflow_id TEXT)
RETURNS TABLE(
    workflow_name TEXT,
    workflow_path TEXT,
    status TEXT,
    current_step_index INTEGER,
    steps JSONB,
    step_results JSONB,
    context JSONB,
    error TEXT,
    log_path TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT wi.workflow_name, wi.workflow_path, wi.status, wi.current_step_index, wi.steps, wi.step_results, wi.context, wi.error, wi.log_path
    FROM workflow_instances wi
    WHERE wi.workflow_id = p_workflow_id;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose StatementBegin
-- List workflow instances for a given project path
CREATE OR REPLACE FUNCTION list_workflow_instances(p_workflow_path TEXT)
RETURNS TABLE(
    workflow_id TEXT,
    workflow_name TEXT,
    status TEXT,
    current_step_index INTEGER,
    steps JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT wi.workflow_id, wi.workflow_name, wi.status, wi.current_step_index, wi.steps
    FROM workflow_instances wi
    WHERE wi.workflow_path = p_workflow_path;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose Down
DROP FUNCTION IF EXISTS list_workflow_instances(TEXT);
DROP FUNCTION IF EXISTS get_workflow_instance(TEXT);
DROP FUNCTION IF EXISTS delete_schedule(TEXT);
DROP FUNCTION IF EXISTS upsert_schedule(TEXT, TEXT, TEXT, JSONB, TEXT, TEXT, BOOLEAN, TIMESTAMPTZ);
DROP FUNCTION IF EXISTS get_enabled_schedules();
DROP FUNCTION IF EXISTS insert_workflow_event(TEXT, TEXT, TEXT, JSONB);
DROP FUNCTION IF EXISTS insert_step_result(TEXT, INTEGER, TEXT, TEXT, TEXT, JSONB, TEXT, TEXT, REAL);
DROP FUNCTION IF EXISTS upsert_workflow_instance(TEXT, TEXT, TEXT, TEXT, INTEGER, JSONB, JSONB, JSONB, TEXT, TEXT);
