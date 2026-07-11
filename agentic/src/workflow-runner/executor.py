"""
Workflow Executor — orchestrates the execution of workflow steps.

The executor walks through each step in a workflow definition and
dispatches to the appropriate handler based on step type.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from handlers import handle_skill_step, handle_tool_step, handle_workflow_step
from loader import load_workflow, WorkflowLoadError
from models import Step, StepResult, StepType, WorkflowDefinition
from state import (
    StateError,
    advance_step,
    append_log,
    create_workflow_state,
    fail_workflow,
    load_workflow_state,
    update_workflow_state,
)


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""
    pass


def execute_workflow(
    workflow: WorkflowDefinition,
    workflow_path: str,
    initial_context: Optional[Dict[str, Any]] = None,
    role_override: Optional[str] = None,
    search_paths: Optional[List[Path]] = None,
    initial_state: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Execute a workflow from start to finish.

    Args:
        workflow: The workflow definition to execute.
        workflow_path: Path to the workflow YAML file (for state management).
        initial_context: Optional initial context values.
        role_override: Optional role name to use for all skill steps.
        search_paths: Additional paths to search for referenced files.
        initial_state: Optional pre-created WorkflowState to resume from.

    Returns:
        A dictionary containing the execution results.
    """
    if initial_state is not None:
        state = initial_state
    else:
        # Create initial state
        state = create_workflow_state(
            workflow_name=workflow.name,
            workflow_path=workflow_path,
            steps=workflow.steps,
            initial_context=initial_context,
        )

    append_log(state, f"Starting workflow: {workflow.name}")
    append_log(state, f"Total steps: {len(workflow.steps)}")

    state.status = "running"
    update_workflow_state(state)

    try:
        while state.current_step_index < len(state.steps):
            step = state.steps[state.current_step_index]
            append_log(
                state,
                f"Step {state.current_step_index + 1}/{len(state.steps)}: "
                f"{step.name} ({step.type.value})",
            )

            # Dispatch to the appropriate handler
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

            # Record the result
            if result.status == "completed":
                # Update context with step output
                if result.output:
                    state.context[step.name] = result.output
                state = advance_step(state, result)
                append_log(state, f"Step '{step.name}' completed")
            else:
                # Step failed
                state = fail_workflow(state, result.error or f"Step '{step.name}' failed")
                append_log(state, f"Step '{step.name}' failed: {result.error}")
                break

    except Exception as e:
        state = fail_workflow(state, f"Unexpected workflow error: {e}")
        append_log(state, f"Workflow failed with unexpected error: {e}")

    # Build the result summary
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
        f"Workflow finished with status: {state.status}"
    )

    return result_summary


def execute_workflow_from_file(
    workflow_path: str,
    initial_context: Optional[Dict[str, Any]] = None,
    role_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Load a workflow from a YAML file and execute it.

    This is the main entry point for the MCP server.

    Args:
        workflow_path: Path to the workflow YAML file.
        initial_context: Optional initial context values.
        role_override: Optional role name to use for all skill steps.

    Returns:
        A dictionary containing the execution results.
    """
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
    )


def get_workflow_status(
    workflow_id: str,
    workflow_path: str,
) -> Dict[str, Any]:
    """
    Get the current status of a running or completed workflow.

    Args:
        workflow_id: The workflow execution ID.
        workflow_path: Path to the workflow YAML file.

    Returns:
        A dictionary with the workflow status.
    """
    state = load_workflow_state(workflow_id, workflow_path)
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