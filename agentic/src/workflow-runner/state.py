"""
Workflow State Manager — manages persistent state for running workflows.

State is stored as JSON files in a .wf/ directory relative to the workflow file.
This allows workflows to be paused, resumed, and inspected.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from models import Step, StepResult, StepType, WorkflowState


class StateError(Exception):
    """Raised when state operations fail."""
    pass


def _get_state_dir(workflow_path: str) -> Path:
    """Get the state directory path for a workflow."""
    wf_path = Path(workflow_path).resolve()
    return wf_path.parent / ".wf"


def _state_file_path(state_dir: Path, workflow_id: str) -> Path:
    """Get the path to a specific workflow state file."""
    return state_dir / f"{workflow_id}.json"


def create_workflow_state(
    workflow_name: str,
    workflow_path: str,
    steps: List[Step],
    initial_context: Optional[Dict[str, Any]] = None,
) -> WorkflowState:
    """
    Create a new workflow state and persist it.

    Args:
        workflow_name: Name of the workflow.
        workflow_path: Path to the workflow YAML file.
        steps: List of steps to execute.
        initial_context: Optional initial context values.

    Returns:
        The created WorkflowState.
    """
    workflow_id = str(uuid.uuid4())[:8]
    state_dir = _get_state_dir(workflow_path)
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
    """Write workflow state to disk."""
    state_dir = _get_state_dir(state.workflow_path)
    state_path = _state_file_path(state_dir, state.workflow_id)

    try:
        with open(state_path, "w") as f:
            f.write(state.model_dump_json(indent=2))
    except IOError as e:
        raise StateError(f"Cannot persist state: {e}")


def load_workflow_state(workflow_id: str, workflow_path: str) -> Optional[WorkflowState]:
    """
    Load a workflow state from disk.

    Args:
        workflow_id: The workflow execution ID.
        workflow_path: Path to the workflow YAML file.

    Returns:
        The WorkflowState if found, None otherwise.
    """
    state_dir = _get_state_dir(workflow_path)
    state_path = _state_file_path(state_dir, workflow_id)

    if not state_path.exists():
        return None

    try:
        with open(state_path, "r") as f:
            data = json.load(f)
        return WorkflowState(**data)
    except (IOError, json.JSONDecodeError) as e:
        raise StateError(f"Cannot load state: {e}")


def update_workflow_state(state: WorkflowState) -> None:
    """Update and persist a workflow state."""
    _persist_state(state)


def advance_step(
    state: WorkflowState,
    result: StepResult,
) -> WorkflowState:
    """
    Record a step result and advance to the next step.

    Args:
        state: Current workflow state.
        result: Result of the completed step.

    Returns:
        Updated workflow state.
    """
    state.step_results.append(result.model_dump())
    state.current_step_index += 1

    if state.current_step_index >= len(state.steps):
        state.status = "completed"
    else:
        state.status = "running"

    _persist_state(state)
    return state


def fail_workflow(state: WorkflowState, error: str) -> WorkflowState:
    """
    Mark a workflow as failed.

    Args:
        state: Current workflow state.
        error: Error message describing the failure.

    Returns:
        Updated workflow state.
    """
    state.status = "failed"
    state.error = error
    _persist_state(state)
    return state


def append_log(state: WorkflowState, message: str) -> None:
    """Append a log message to the workflow log file."""
    if not state.log_path:
        return

    log_path = Path(state.log_path)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_path, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except IOError:
        pass  # Logging failure should not break execution


def list_workflow_states(workflow_path: str) -> List[Dict[str, Any]]:
    """
    List all workflow states for a given workflow file.

    Args:
        workflow_path: Path to the workflow YAML file.

    Returns:
        List of workflow state summaries.
    """
    state_dir = _get_state_dir(workflow_path)
    if not state_dir.exists():
        return []

    states = []
    for f in state_dir.glob("*.json"):
        try:
            with open(f, "r") as fh:
                data = json.load(fh)
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