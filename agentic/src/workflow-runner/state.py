"""
Workflow State Manager — backward-compatible wrapper around db.py.

All callers (executor, tests, server) can continue importing from
`state` while persistence migrates from file-based `.wf/` to Postgres
with automatic file fallback for local inspection.
"""

from __future__ import annotations

from db import (  # noqa: F401
    advance_step,
    append_log,
    create_workflow_state,
    fail_workflow,
    load_workflow_state,
    list_workflow_states,
    pause_workflow,
    resume_workflow,
    stop_workflow,
    update_workflow_state,
)


class StateError(Exception):
    """Raised when state operations fail."""
    pass
