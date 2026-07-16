"""
Skill Handler — composes prompts for skill steps and executes them
via the LangGraph runtime.

For skill steps, the handler composes the prompt and sends it to the
runtime client for execution, then returns the result.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from models import Step, StepResult, StepType, WorkflowDefinition
from composer import compose_skill_prompt, CompositionError


def handle_skill_step(
    step: Step,
    workflow: WorkflowDefinition,
    context: Dict[str, Any],
    role_override: Optional[str] = None,
) -> StepResult:
    """
    Handle a skill step by composing a prompt and executing it via the runtime.

    Args:
        step: The skill step to handle.
        workflow: The parent workflow definition.
        context: Current workflow context (inputs, previous outputs).
        role_override: Optional role name override.

    Returns:
        StepResult with the execution output.
    """
    start_time = time.time()
    result = StepResult(
        step_name=step.name,
        step_type=StepType.SKILL,
        status="running",
    )

    try:
        prompt = compose_skill_prompt(step, workflow, context, role_override)
        result.composed_prompt = prompt

        runtime_output = _execute_prompt(prompt)
        if runtime_output.get("status") == "completed":
            result.status = "completed"
            result.output = runtime_output.get("output")
        else:
            result.status = "failed"
            result.error = runtime_output.get("error") or "Runtime execution failed"

    except CompositionError as e:
        result.status = "failed"
        result.error = str(e)
    except Exception as e:
        result.status = "failed"
        result.error = f"Unexpected error executing skill step: {e}"

    result.duration_seconds = time.time() - start_time
    return result


def _execute_prompt(prompt: str) -> Dict[str, Any]:
    try:
        from runtime_client import run as runtime_run
    except ImportError:
        return {
            "status": "completed",
            "output": {"prompt": prompt, "simulated": True},
        }

    try:
        return runtime_run(prompt)
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
        }
