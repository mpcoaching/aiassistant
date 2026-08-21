"""
Capability execution (Increment 2).

Provides a single function for executing compiled capabilities.
Does not create an executor class; execution is a function that
imports the capability module and invokes its run() entrypoint.
"""

from __future__ import annotations

import importlib
from typing import Any

from capabilities import Capability, ExecutionMode
from pydantic import BaseModel


class ExecutionResult(BaseModel):
    """Result of executing a capability."""

    outputs: dict[str, Any]
    artifacts: list[str] = []
    telemetry: dict[str, Any] = {}


def execute_capability(capability: Capability, context: dict[str, Any]) -> ExecutionResult:
    """Execute a compiled capability and return the result.

    Args:
        capability: The capability to execute. Must have execution_mode=compiled.
        context: Execution context dict passed to the capability's run() function.

    Returns:
        ExecutionResult with outputs, artifacts, and telemetry.

    Raises:
        ValueError: If capability execution_mode is not compiled.
        FileNotFoundError: If the capability module cannot be imported.
        AttributeError: If the capability module lacks a run() callable.
    """
    if capability.execution_mode != ExecutionMode.COMPILED:
        raise ValueError(
            f"Unsupported execution mode: {capability.execution_mode}. "
            "Only compiled capabilities can be executed in this slice."
        )

    if capability.compiled_ref is None:
        raise ValueError(
            f"Capability {capability.name} has no compiled_ref. "
            "Register the capability with a compiled module path before execution."
        )

    module_path = capability.compiled_ref.module_path
    entrypoint = capability.compiled_ref.entrypoint or "run"

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise FileNotFoundError(
            f"Cannot import capability module: {module_path}"
        ) from exc

    run_fn = getattr(module, entrypoint, None)
    if run_fn is None or not callable(run_fn):
        raise AttributeError(
            f"Capability module {module_path} does not expose a callable '{entrypoint}'"
        )

    outputs = run_fn(context)

    return ExecutionResult(
        outputs=outputs or {},
        artifacts=[],
        telemetry={
            "capability_id": capability.id,
            "capability_name": capability.name,
            "execution_mode": capability.execution_mode.value,
            "module_path": module_path,
        },
    )
