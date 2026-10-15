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
from pydantic import BaseModel

from capability_deployment import CapabilityDeployment, ExecutionMode


class ExecutionResult(BaseModel):
    """Result of executing a capability."""

    outputs: dict[str, Any]
    artifacts: list[str] = []
    telemetry: dict[str, Any] = {}


def execute_capability(capability: Capability, context: dict[str, Any], deployment: CapabilityDeployment | None = None) -> ExecutionResult:
    """Execute a compiled capability and return the result.

    Args:
        capability: The capability to execute.
        context: Execution context dict passed to the capability's run() function.
        deployment: Optional CapabilityDeployment with compiled_ref and execution metadata.

    Returns:
        ExecutionResult with outputs, artifacts, and telemetry.

    Raises:
        ValueError: If capability cannot be executed.
        FileNotFoundError: If the capability module cannot be imported.
        AttributeError: If the capability module lacks a run() callable.
    """
    if deployment is None:
        raise ValueError(
            "execute_capability requires a CapabilityDeployment. "
            "Pass deployment with compiled_ref."
        )

    compiled_ref = deployment.compiled_ref
    if compiled_ref is None:
        raise ValueError("execute_capability requires compiled_ref in deployment.")

    module_path = compiled_ref.module_path
    entrypoint = compiled_ref.entrypoint or "run"

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
