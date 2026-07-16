"""
Workflow Handler — handles nested workflow steps.

When a workflow step references another workflow, this handler
loads the sub-workflow and executes it recursively.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loader import load_workflow, resolve_workflow_path, WorkflowLoadError
from models import Step, StepResult, StepType


def handle_workflow_step(
    step: Step,
    context: Dict[str, Any],
    search_paths: Optional[List[Path]] = None,
) -> StepResult:
    """
    Handle a workflow step by loading and executing the sub-workflow.

    Args:
        step: The workflow step to handle.
        context: Current workflow context (passed to sub-workflow).
        search_paths: Additional paths to search for workflow files.

    Returns:
        StepResult with the sub-workflow execution results.
    """
    start_time = time.time()
    result = StepResult(
        step_name=step.name,
        step_type=StepType.WORKFLOW,
        status="running",
    )

    try:
        # Lazy import to avoid circular dependency (executor -> handlers -> executor)
        from executor import execute_workflow  # type: ignore[import-untyped]

        # Resolve the sub-workflow file path
        wf_path = resolve_workflow_path(step.uses, search_paths)
        if wf_path is None:
            # Try as a direct file path
            wf_path = Path(step.uses)
            if not wf_path.exists():
                result.status = "failed"
                result.error = (
                    f"Sub-workflow '{step.uses}' not found. "
                    f"Searched workflows directory and as direct path."
                )
                result.duration_seconds = time.time() - start_time
                return result

        # Load the sub-workflow
        sub_workflow = load_workflow(str(wf_path))

        # Execute the sub-workflow recursively
        sub_results = execute_workflow(
            workflow=sub_workflow,
            workflow_path=str(wf_path),
            initial_context=context,
        )

        # Check if the sub-workflow succeeded
        if sub_results["status"] == "completed":
            result.status = "completed"
            result.output = {
                "sub_workflow": step.uses,
                "step_results": sub_results.get("step_results", []),
                "final_context": sub_results.get("context", {}),
            }
        else:
            result.status = "failed"
            result.error = (
                f"Sub-workflow '{step.uses}' failed: "
                f"{sub_results.get('error', 'Unknown error')}"
            )
            result.output = sub_results

    except WorkflowLoadError as e:
        result.status = "failed"
        result.error = f"Failed to load sub-workflow '{step.uses}': {e}"
    except Exception as e:
        result.status = "failed"
        result.error = (
            f"Unexpected error executing sub-workflow '{step.uses}': {e}"
        )
    finally:
        result.duration_seconds = time.time() - start_time

    return result