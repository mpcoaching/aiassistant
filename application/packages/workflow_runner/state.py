"""
Workflow State Manager — backward-compatible wrapper around db.py.

All callers (executor, tests, server) can continue importing from
`state` while persistence migrates from file-based `.wf/` to Postgres
with automatic file fallback for local inspectability.
"""

from __future__ import annotations

from typing import Any

from db import (
    advance_step as _db_advance_step,
)
from db import (
    append_log as _db_append_log,
)
from db import (
    create_workflow_state as _db_create_workflow_state,
)
from db import (
    fail_workflow as _db_fail_workflow,
)
from db import (
    list_workflow_states as _db_list_workflow_states,
)
from db import (
    load_workflow_state as _db_load_workflow_state,
)
from db import (
    pause_workflow as _db_pause_workflow,
)
from db import (
    record_step_result as _db_record_step_result,
)
from db import (
    resume_workflow as _db_resume_workflow,
)
from db import (
    stop_workflow as _db_stop_workflow,
)
from db import (
    update_workflow_state as _db_update_workflow_state,
)


def create_workflow_state(
    workflow_name: str,
    workflow_path: str,
    steps: Any,
    initial_context: dict | None = None,
    database_url: str | None = None,
) -> Any:
    return _db_create_workflow_state(
        workflow_name=workflow_name,
        workflow_path=workflow_path,
        steps=steps,
        initial_context=initial_context,
        database_url=database_url,
    )


def load_workflow_state(workflow_id: str, workflow_path: str, database_url: str | None = None) -> Any:
    return _db_load_workflow_state(workflow_id, workflow_path, database_url=database_url)


def list_workflow_states(workflow_path: str, database_url: str | None = None) -> Any:
    return _db_list_workflow_states(workflow_path, database_url=database_url)


def update_workflow_state(state: Any, database_url: str | None = None) -> None:
    _db_update_workflow_state(state, database_url=database_url)


def advance_step(state: Any, result: Any, database_url: str | None = None) -> Any:
    return _db_advance_step(state, result, database_url=database_url)


def fail_workflow(state: Any, error: str, database_url: str | None = None) -> Any:
    return _db_fail_workflow(state, error, database_url=database_url)


def pause_workflow(state: Any, reason: str = "user_requested", database_url: str | None = None) -> Any:
    return _db_pause_workflow(state, reason=reason, database_url=database_url)


def resume_workflow(state: Any, database_url: str | None = None) -> Any:
    return _db_resume_workflow(state, database_url=database_url)


def stop_workflow(state: Any, reason: str = "user_requested", database_url: str | None = None) -> Any:
    return _db_stop_workflow(state, reason=reason, database_url=database_url)


def record_step_result(state: Any, result: Any, step_index: int, database_url: str | None = None) -> None:
    _db_record_step_result(state, result, step_index, database_url=database_url)


def append_log(state: Any, message: str, database_url: str | None = None) -> None:
    _db_append_log(state, message, database_url=database_url)


class StateError(Exception):
    """Raised when state operations fail."""
