"""
Skill Handler — composes prompts for skill steps.

For skill steps, the handler does NOT execute the prompt.
It composes it and returns it to the caller (the MCP server),
which passes it to the calling agent for execution.
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
    Handle a skill step by composing a prompt.

    This does NOT execute the skill — it composes the prompt and returns it.
    The calling agent is responsible for executing the prompt.

    Args:
        step: The skill step to handle.
        workflow: The parent workflow definition.
        context: Current workflow context (inputs, previous outputs).
        role_override: Optional role name override.

    Returns:
        StepResult with the composed prompt (in 'output' field).
    """
    start_time = time.time()
    result = StepResult(
        step_name=step.name,
        step_type=StepType.SKILL,
        status="running",
    )

    try:
        prompt = compose_skill_prompt(step, workflow, context, role_override)
        result.status = "completed"
        result.composed_prompt = prompt
        result.output = {
            "prompt": prompt,
            "step_name": step.name,
            "skill": step.uses,
            "status": "ready_for_execution",
        }
    except CompositionError as e:
        result.status = "failed"
        result.error = str(e)
    except Exception as e:
        result.status = "failed"
        result.error = f"Unexpected error composing skill prompt: {e}"

    result.duration_seconds = time.time() - start_time
    return result