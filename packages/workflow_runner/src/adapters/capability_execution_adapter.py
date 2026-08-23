"""
Adapter: contracts.CapabilityExecutionPort -> workflow_runner execute_capability().

Translates capability_id/context/actor_context into a Capability + CapabilityDeployment,
delegating to execute_capability(), and returning ExecutionResult.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from capabilities import CapabilityRegistry
from capability import Capability
from contracts.capability_execution import ExecutionResult
from contracts.invocation_recorder import InvocationRecorder
from execution_authorisation import ExecutionAuthorisationPort

from capability_deployment import CapabilityDeployment
from executor import execute_capability


class CapabilityExecutionAdapter:
    def __init__(
        self,
        registry: CapabilityRegistry,
        deployment_factory: Callable[[Capability], CapabilityDeployment | None],
        authorisation_port: ExecutionAuthorisationPort | None = None,
        invocation_recorder: InvocationRecorder | None = None,
    ) -> None:
        self._registry = registry
        self._deployment_factory = deployment_factory
        self._authorisation_port = authorisation_port
        self._invocation_recorder = invocation_recorder

    def execute(self, capability_id: str, context: dict[str, Any], actor_context: dict[str, Any]) -> ExecutionResult:
        capability = self._registry.get(capability_id)
        if capability is None:
            result = ExecutionResult(
                outputs={"error": f"Capability not found: {capability_id}"},
                artifacts=[],
                telemetry={"error": "capability_not_found"},
            )
            if self._invocation_recorder is not None:
                self._invocation_recorder.record_invocation(capability_id, result, actor_context)
            return result

        authorisation_error = self._check_authorisation(capability_id, actor_context)
        if authorisation_error:
            result = ExecutionResult(
                outputs=authorisation_error,
                artifacts=[],
                telemetry={"error": "execution_not_authorised"},
            )
            if self._invocation_recorder is not None:
                self._invocation_recorder.record_invocation(capability_id, result, actor_context)
            return result

        deployment = self._deployment_factory(capability)
        if deployment is None:
            result = ExecutionResult(
                outputs={"error": f"No deployment for capability: {capability_id}"},
                artifacts=[],
                telemetry={"error": "no_deployment"},
            )
            if self._invocation_recorder is not None:
                self._invocation_recorder.record_invocation(capability_id, result, actor_context)
            return result
        result = execute_capability(capability, context, deployment)
        if self._invocation_recorder is not None:
            self._invocation_recorder.record_invocation(capability_id, result, actor_context)
        return result

    def _check_authorisation(self, capability_id: str, actor_context: dict[str, Any]) -> dict[str, Any] | None:
        if self._authorisation_port is None:
            return None
        actor_id = actor_context.get("actor_id")
        actor_type = actor_context.get("actor_type", "agent")
        if not actor_id:
            return None
        result = self._authorisation_port.is_authorised(actor_id, actor_type, capability_id)
        if not result.authorised:
            return {"error": f"Execution not authorised: {result.reason}"}
        return None
