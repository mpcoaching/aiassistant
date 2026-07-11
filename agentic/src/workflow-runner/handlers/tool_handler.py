"""
Tool Handler — executes tool steps.

Tool steps run shell commands directly and capture their output.
This is the deterministic part of the workflow system — tools can be executed
without any AI involvement.

SECURITY: the command produced by the composer is parsed with `shlex` and
executed with `shell=False` against an explicit allowlist. The production
execution path runs server-side in the sandboxed Agent Execution Environment;
this handler is only exercised by the local dev-stub. Never expand the
allowlist for production use — untrusted workflow YAML must never reach this
code path with arbitrary commands.
"""

from __future__ import annotations

import shlex
import subprocess  # nosec
import time
from typing import Any, Dict, List

from composer import CompositionError, compose_tool_command
from models import Step, StepResult, StepType

# Dev-only allowlist. The production execution path runs server-side in the
# sandboxed Agent Execution Environment; this handler is only used by the local
# dev-stub. Never expand this list for production use.
DEFAULT_TOOL_ALLOWLIST = frozenset(
    {
        "echo",
        "sh",
        "bash",
        "cat",
        "ls",
        "true",
        "false",
        "python",
        "python3",
        "pip",
    }
)


def _parse_command(step: Step, context: Dict[str, Any]) -> List[str]:
    """
    Build a safe argv list for the tool step.

    Raises CompositionError if the command is empty or the command basename is
    not on the allowlist.
    """
    raw = compose_tool_command(step, context)
    if not raw or not raw.strip():
        raise CompositionError("Empty tool command from tool step")

    try:
        argv = shlex.split(raw)
    except ValueError as e:
        raise CompositionError(f"Cannot parse tool command: {e}")

    if not argv:
        raise CompositionError("Empty tool command from tool step")

    basename = argv[0].rsplit("/", 1)[-1]
    if basename not in DEFAULT_TOOL_ALLOWLIST:
        raise CompositionError(f"Tool command not allowed: {basename}")

    return argv


def handle_tool_step(
    step: Step,
    context: Dict[str, Any],
) -> StepResult:
    """
    Handle a tool step by executing a shell command.

    The command is composed from the step definition and context, then executed
    as a subprocess with shell=False (no shell interpretation). Output is
    captured and returned.

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
        argv = _parse_command(step, context)
    except CompositionError as e:
        result.status = "failed"
        result.error = str(e)
        result.duration_seconds = time.time() - start_time
        return result

    try:
        completed = subprocess.run(  # nosec - shell=False, allowlisted argv
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        output = {
            "command": " ".join(argv),
            "argv": argv,
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
