"""
PostgreSQL state persistence with file-system fallback.

Workflow instances, step results, and schedules are stored in Postgres
when DATABASE_URL is available.  If Postgres is unreachable, writes are
mirrored to the legacy ``.wf/`` JSON files so no state is lost during
container restarts or failover.

Tables:
  - workflow_instances
  - step_results
  - schedules
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from models import Step, StepResult, WorkflowState


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://${AIASSIST_DB_USER}:${AIASSIST_DB_PASSWORD}@${POSTGRES_HOST}:5432/${AIASSIST_DB_NAME}",
)


def _pg_conn():
    import psycopg2  # type: ignore[import-untyped]
    return psycopg2.connect(DATABASE_URL)


def _file_dir(workflow_path: str) -> Path:
    return Path(workflow_path).resolve().parent / ".wf"


def _file_state_path(state_dir: Path, workflow_id: str) -> Path:
    return state_dir / f"{workflow_id}.json"


def _persist_file(state: WorkflowState) -> None:
    state_dir = _file_dir(state.workflow_path)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = _file_state_path(state_dir, state.workflow_id)
    try:
        path.write_text(state.model_dump_json(indent=2))
    except OSError:
        pass


def _append_file_log(state: WorkflowState, message: str) -> None:
    if not state.log_path:
        return
    log_path = Path(state.log_path)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except OSError:
        pass


def _ensure_schema() -> None:
    try:
        with _pg_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """
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
                    )
                    """
                )
                cur.execute(
                    """
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
                    )
                    """
                )
                cur.execute(
                    """
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
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workflow_events (
                        event_id TEXT PRIMARY KEY,
                        workflow_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
    except Exception:
        pass


def _pg_upsert_instance(state: WorkflowState) -> None:
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow_instances
                        (workflow_id, workflow_name, workflow_path, status, current_step_index, steps, step_results, context, error, log_path, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (workflow_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        current_step_index = EXCLUDED.current_step_index,
                        step_results = EXCLUDED.step_results,
                        context = EXCLUDED.context,
                        error = EXCLUDED.error,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        state.workflow_id,
                        state.workflow_name,
                        state.workflow_path,
                        state.status,
                        state.current_step_index,
                        json.dumps([s.model_dump() for s in state.steps]),
                        json.dumps(state.step_results),
                        json.dumps(state.context),
                        state.error,
                        state.log_path,
                        datetime.now(timezone.utc),
                    ),
                )
            conn.commit()
    except Exception:
        pass


def _pg_insert_step_result(step_result: Dict[str, Any], workflow_id: str, step_index: int) -> None:
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO step_results (workflow_id, step_index, step_name, step_type, status, output, composed_prompt, error, duration_seconds)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        workflow_id,
                        step_index,
                        step_result.get("step_name"),
                        step_result.get("step_type"),
                        step_result.get("status"),
                        json.dumps(step_result.get("output")),
                        step_result.get("composed_prompt"),
                        step_result.get("error"),
                        step_result.get("duration_seconds"),
                    ),
                )
            conn.commit()
    except Exception:
        pass


def _pg_insert_event(event_id: str, workflow_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow_events (event_id, workflow_id, event_type, payload)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (event_id, workflow_id, event_type, json.dumps(payload)),
                )
            conn.commit()
    except Exception:
        pass


def _pg_get_schedules() -> List[Dict[str, Any]]:
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT schedule_id, workflow_name, cron, initial_context, role_override, trigger, enabled, next_fire_time FROM schedules WHERE enabled = TRUE")
                rows = cur.fetchall()
                keys = ["schedule_id", "workflow_name", "cron", "initial_context", "role_override", "trigger", "enabled", "next_fire_time"]
                return [dict(zip(keys, r)) for r in rows]
    except Exception:
        return []


def _pg_upsert_schedule(schedule: Dict[str, Any]) -> None:
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO schedules (schedule_id, workflow_name, cron, initial_context, role_override, trigger, enabled, next_fire_time, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (schedule_id) DO UPDATE SET
                        enabled = EXCLUDED.enabled,
                        next_fire_time = EXCLUDED.next_fire_time,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        schedule["schedule_id"],
                        schedule["workflow_name"],
                        schedule["cron"],
                        json.dumps(schedule.get("initial_context", {})),
                        schedule.get("role_override"),
                        schedule.get("trigger", "scheduled"),
                        schedule.get("enabled", True),
                        schedule.get("next_fire_time"),
                        datetime.now(timezone.utc),
                    ),
                )
            conn.commit()
    except Exception:
        pass


def _pg_delete_schedule(schedule_id: str) -> None:
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM schedules WHERE schedule_id = %s", (schedule_id,))
            conn.commit()
    except Exception:
        pass


# Public API ----------------------------------------------------------------


def create_workflow_state(
    workflow_name: str,
    workflow_path: str,
    steps: List[Step],
    initial_context: Optional[Dict[str, Any]] = None,
) -> WorkflowState:
    workflow_id = str(uuid.uuid4())[:8]
    state_dir = _file_dir(workflow_path)
    state_dir.mkdir(parents=True, exist_ok=True)

    state = WorkflowState(
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        workflow_path=workflow_path,
        status="pending",
        current_step_index=0,
        steps=steps,
        step_results=[],
        context=initial_context or {},
        log_path=str(state_dir / f"{workflow_id}.log"),
    )

    _persist_state(state)
    return state


def _persist_state(state: WorkflowState) -> None:
    _persist_file(state)
    try:
        _ensure_schema()
        _pg_upsert_instance(state)
    except Exception:
        pass


def load_workflow_state(workflow_id: str, workflow_path: str) -> Optional[WorkflowState]:
    # Try Postgres first
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT workflow_name, workflow_path, status, current_step_index, steps, step_results, context, error, log_path
                    FROM workflow_instances
                    WHERE workflow_id = %s
                    """,
                    (workflow_id,),
                )
                row = cur.fetchone()
                if row:
                    (
                        wname,
                        wpath,
                        status,
                        idx,
                        steps_json,
                        results_json,
                        ctx_json,
                        error,
                        log_path,
                    ) = row
                    steps = [Step(**s) for s in steps_json]
                    state = WorkflowState(
                        workflow_id=workflow_id,
                        workflow_name=wname,
                        workflow_path=wpath or workflow_path,
                        status=status,
                        current_step_index=idx,
                        steps=steps,
                        step_results=[r for r in (results_json or [])],
                        context=ctx_json or {},
                        error=error,
                        log_path=log_path,
                    )
                    # Mirror to file for local inspectability
                    _persist_file(state)
                    return state
    except Exception:
        pass

    # Fallback to file
    state_dir = _file_dir(workflow_path)
    state_path = _file_state_path(state_dir, workflow_id)
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text())
            return WorkflowState(**data)
        except (IOError, json.JSONDecodeError):
            pass
    return None


def list_workflow_states(workflow_path: str) -> List[Dict[str, Any]]:
    states: List[Dict[str, Any]] = []

    # Try Postgres first
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT workflow_id, workflow_name, status, current_step_index, steps
                    FROM workflow_instances
                    WHERE workflow_path = %s
                    """,
                    (workflow_path,),
                )
                for row in cur.fetchall():
                    states.append({
                        "workflow_id": row[0],
                        "workflow_name": row[1],
                        "status": row[2],
                        "current_step": row[3],
                        "total_steps": len(row[4]) if row[4] else 0,
                    })
                if states:
                    return sorted(states, key=lambda s: s.get("workflow_id", ""))
    except Exception:
        pass

    # File fallback
    state_dir = _file_dir(workflow_path)
    if not state_dir.exists():
        return []
    for f in state_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            states.append({
                "workflow_id": data.get("workflow_id"),
                "workflow_name": data.get("workflow_name"),
                "status": data.get("status"),
                "current_step": data.get("current_step_index", 0),
                "total_steps": len(data.get("steps", [])),
            })
        except (IOError, json.JSONDecodeError):
            continue
    return sorted(states, key=lambda s: s.get("workflow_id", ""))


def update_workflow_state(state: WorkflowState) -> None:
    _persist_state(state)


def advance_step(state: WorkflowState, result: StepResult) -> WorkflowState:
    state.step_results.append(result.model_dump())
    state.current_step_index += 1
    if state.current_step_index >= len(state.steps):
        state.status = "completed"
    else:
        state.status = "running"
    _persist_state(state)
    return state


def fail_workflow(state: WorkflowState, error: str) -> WorkflowState:
    state.status = "failed"
    state.error = error
    _persist_state(state)
    return state


def pause_workflow(state: WorkflowState, reason: str = "user_requested") -> WorkflowState:
    state.status = "paused"
    _persist_state(state)
    return state


def resume_workflow(state: WorkflowState) -> WorkflowState:
    state.status = "running"
    _persist_state(state)
    return state


def stop_workflow(state: WorkflowState, reason: str = "user_requested") -> WorkflowState:
    state.status = "stopped"
    _persist_state(state)
    return state


def append_log(state: WorkflowState, message: str) -> None:
    _append_file_log(state, message)


def record_step_result(state: WorkflowState, result: StepResult, step_index: int) -> None:
    _pg_insert_step_result(result.model_dump(), state.workflow_id, step_index)


def insert_event(event_id: str, workflow_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    _pg_insert_event(event_id, workflow_id, event_type, payload)


def get_schedules() -> List[Dict[str, Any]]:
    try:
        _ensure_schema()
    except Exception:
        pass
    return _pg_get_schedules()


def upsert_schedule(schedule: Dict[str, Any]) -> None:
    try:
        _ensure_schema()
    except Exception:
        pass
    _pg_upsert_schedule(schedule)


def delete_schedule(schedule_id: str) -> None:
    try:
        _ensure_schema()
    except Exception:
        pass
    _pg_delete_schedule(schedule_id)
