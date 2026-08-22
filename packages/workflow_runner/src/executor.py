"""
Capability execution (Increment 2, moved to Operations plane in Increment 14).

Provides a single function for executing compiled capabilities.
Execution is an operational concern. The Capability domain model no longer
carries execution_mode, compiled_ref, or ai_spec. Those live in CapabilityDeployment.
"""

from __future__ import annotations

import importlib
from typing import Any

from capability import Capability
from capability_deployment import CompiledRef, ExecutionMode
from pydantic import BaseModel, Field


class ExecutionResult(BaseModel):
    """Result of executing a capability."""

    outputs: dict[str, Any]
    artifacts: list[str] = []
    telemetry: dict[str, Any] = {}


def execute_capability(capability: Capability, context: dict[str, Any], deployment: CompiledRef | None = None) -> ExecutionResult:
    """Execute a compiled capability and return the result.

    Args:
        capability: The capability to execute.
        context: Execution context dict passed to the capability's run() function.
        deployment: Optional CompiledRef with module_path and entrypoint.

    Returns:
        ExecutionResult with outputs, artifacts, and telemetry.

    Raises:
        ValueError: If capability cannot be executed.
        FileNotFoundError: If the capability module cannot be imported.
        AttributeError: If the capability module lacks a run() callable.
    """
    if deployment is None:
        raise ValueError(
            "execute_capability requires a CompiledRef deployment. "
            "Pass deployment from CapabilityDeployment.compiled_ref."
        )

    module_path = deployment.module_path
    entrypoint = deployment.entrypoint or "run"

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
            "execution_mode": ExecutionMode.COMPILED.value,
            "module_path": module_path,
        },
    )
