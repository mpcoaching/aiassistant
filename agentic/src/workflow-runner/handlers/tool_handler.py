"""
Tool Handler — executes tool steps.

Tool steps run shell commands directly and capture their output.
This is the deterministic part of the workflow system — tools
can be executed without any AI involvement.
"""

from __future__ import annotations

import subprocess  # nosec
import time
from typing import Any, Dict

from models import Step, StepResult, StepType
from composer import compose_tool_command, CompositionError


def handle_tool_step(
    step: Step,
    context: Dict[str, Any],
) -> StepResult:
    """
    Handle a tool step by executing a shell command.

    The command is composed from the step definition and context,
    then executed as a subprocess. Output is captured and returned.

    Args:
        step: The tool step to handle.
        context: Current workflow context for variable substitution.

    Returns:
        StepResult with the command output.
    """
    start_time = time.time()
    result = StepResult(
        step_name=step.name,
        step_type=StepType.TOOL,
        status="running",
    )

    try:
        command = compose_tool_command(step, context)

        if not command:
            result.status = "failed"
            result.error = "Empty command from tool step"
            result.duration_seconds = time.time() - start_time
            return result

        # Execute the command
        completed = subprocess.run(  # nosec
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        output = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

        if completed.returncode == 0:
            result.status = "completed"
            result.output = output
        else:
            result.status = "failed"
            result.output = output
            result.error = (
                f"Tool '{step.uses}' exited with code {completed.returncode}: "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )

    except subprocess.TimeoutExpired:
        result.status = "failed"
        result.error = f"Tool '{step.uses}' timed out after 300 seconds"
    except FileNotFoundError as e:
        result.status = "failed"
        result.error = f"Tool '{step.uses}' not found: {e}"
    except Exception as e:
        result.status = "failed"
        result.error = f"Unexpected error executing tool '{step.uses}': {e}"
    finally:
        result.duration_seconds = time.time() - start_time

    return result