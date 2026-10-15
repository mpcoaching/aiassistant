"""
Workflow Executor — orchestrates the execution of workflow steps.

The executor walks through each step in a workflow definition and
dispatches to the appropriate handler based on step type.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from handlers import handle_skill_step, handle_tool_step, handle_workflow_step
from loader import WorkflowLoadError, load_workflow
from models import Step, StepResult, StepType, WorkflowDefinition
from state import (
    advance_step,
    append_log,
    create_workflow_state,
    fail_workflow,
    load_workflow_state,
    update_workflow_state,
)


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""


def execute_workflow(
    workflow: WorkflowDefinition,
    workflow_path: str,
    initial_context: dict[str, Any] | None = None,
    role_override: str | None = None,
    search_paths: list[Path] | None = None,
    initial_state: Any | None = None,
    on_step_start: Callable[[Step, int], None] | None = None,
    on_step_complete: Callable[[Step, StepResult, int], None] | None = None,
    database_url: str | None = None,
) -> dict[str, Any]:
    """
    Execute a workflow from start to finish.

    Args:
        workflow: The workflow definition to execute.
        workflow_path: Path to the workflow YAML file (for state management).
        initial_context: Optional initial context values.
        role_override: Optional role name to use for all skill steps.
        search_paths: Additional paths to search for referenced files.
        initial_state: Optional pre-created WorkflowState to resume from.
        on_step_start: Optional callback invoked with (step, index) before a
            step executes. Kept outside the executor to stay framework-agnostic.
        on_step_complete: Optional callback invoked with (step, result, index)
            after a step finishes (success or failure).
        database_url: Optional database URL for persistence.

    Returns:
        A dictionary containing the execution results.
    """
    if initial_state is not None:
        state = initial_state
    else:
        state = create_workflow_state(
            workflow_name=workflow.name,
            workflow_path=workflow_path,
            steps=workflow.steps,
            initial_context=initial_context,
            database_url=database_url,
        )

    append_log(state, f"Starting workflow: {workflow.name}", database_url=database_url)
    append_log(state, f"Total steps: {len(workflow.steps)}", database_url=database_url)

    state.status = "running"
    update_workflow_state(state, database_url=database_url)

    try:
        while state.current_step_index < len(state.steps):
            step = state.steps[state.current_step_index]
            append_log(
                state,
                f"Step {state.current_step_index + 1}/{len(state.steps)}: "
                f"{step.name} ({step.type.value})",
                database_url=database_url,
            )

            if on_step_start is not None:
                on_step_start(step, state.current_step_index)

            if step.type == StepType.SKILL:
                result = handle_skill_step(step, workflow, state.context, role_override)
            elif step.type == StepType.TOOL:
                result = handle_tool_step(step, state.context)
            elif step.type == StepType.WORKFLOW:
                result = handle_workflow_step(step, state.context, search_paths)
            else:
                result = StepResult(
                    step_name=step.name,
                    step_type=step.type,
                    status="failed",
                    error=f"Unknown step type: {step.type}",
                )

            if on_step_complete is not None:
                on_step_complete(step, result, state.current_step_index)

            if result.status == "completed":
                if result.output:
                    state.context[step.name] = result.output
                state = advance_step(state, result, database_url=database_url)
                append_log(state, f"Step '{step.name}' completed", database_url=database_url)
            else:
                state = fail_workflow(state, result.error or f"Step '{step.name}' failed", database_url=database_url)
                append_log(state, f"Step '{step.name}' failed: {result.error}", database_url=database_url)
                break

    except Exception as e:  # noqa: BLE001
        state = fail_workflow(state, f"Unexpected workflow error: {e}", database_url=database_url)
        append_log(state, f"Workflow failed with unexpected error: {e}", database_url=database_url)

    result_summary = {
        "workflow_id": state.workflow_id,
        "workflow_name": workflow.name,
        "status": state.status,
        "step_results": state.step_results,
        "context": state.context,
        "error": state.error,
        "total_steps": len(workflow.steps),
        "completed_steps": state.current_step_index,
    }

    append_log(
        state,
        f"Workflow finished with status: {state.status}",
        database_url=database_url,
    )

    return result_summary


def execute_workflow_from_file(
    workflow_path: str,
    initial_context: dict[str, Any] | None = None,
    role_override: str | None = None,
    database_url: str | None = None,
) -> dict[str, Any]:
    try:
        workflow = load_workflow(workflow_path)
    except WorkflowLoadError as e:
        return {
            "status": "failed",
            "error": str(e),
            "workflow_name": None,
            "step_results": [],
            "context": {},
        }

    return execute_workflow(
        workflow=workflow,
        workflow_path=workflow_path,
        initial_context=initial_context,
        role_override=role_override,
        database_url=database_url,
    )


def get_workflow_status(
    workflow_id: str,
    workflow_path: str,
    database_url: str | None = None,
) -> dict[str, Any]:
    state = load_workflow_state(workflow_id, workflow_path, database_url=database_url)
    if state is None:
        return {
            "found": False,
            "error": f"Workflow '{workflow_id}' not found",
        }

    return {
        "found": True,
        "workflow_id": state.workflow_id,
        "workflow_name": state.workflow_name,
        "status": state.status,
        "current_step_index": state.current_step_index,
        "total_steps": len(state.steps),
        "error": state.error,
        "step_results": state.step_results,
    }
