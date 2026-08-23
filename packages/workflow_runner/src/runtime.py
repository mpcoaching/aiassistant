"""
Pattern Runtime adapter (Phase 3, contract C10 / RUNTIME-MAPPING.md).

Executes pattern steps by invoking Capabilities via the internal agentic API.
Tier 2 (in-process) calls the module's `run(context)` directly; Tier 3 (bus)
publishes a CapabilityRequest to the Event Bus and returns a simulated reply.

Execution metadata comes from CapabilityDeployment, not from the Capability domain model.
"""

from __future__ import annotations

import logging
from typing import Any

from capabilities import CapabilityRegistry
from capability import Capability
from contracts.capability_execution import ExecutionResult
from execution_authorisation import ExecutionAuthorisationPort
from invocation_recorder import InvocationRecorder

from bus import CapabilityReply, CapabilityRequest, EventBus
from capability_deployment import CapabilityDeployment, ExecutionMode, Transport

logger = logging.getLogger("workflow-engine.runtime")


class PatternRuntime:
    """Executes pattern steps as Capability invocations."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        bus: EventBus | None = None,
        authorisation_port: ExecutionAuthorisationPort | None = None,
        invocation_recorder: InvocationRecorder | None = None,
    ) -> None:
        self._registry = registry
        self._bus = bus
        self._authorisation_port = authorisation_port
        self._invocation_recorder = invocation_recorder

    def invoke_step(
        self,
        capability_id: str,
        inputs: dict[str, Any],
        deployment: CapabilityDeployment | None = None,
        actor_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cap = self._registry.get(capability_id)
        if cap is None:
            return {"status": "failed", "error": f"Capability not found: {capability_id}"}

        if deployment is None:
            return {"status": "failed", "error": "CapabilityDeployment required for execution. Pass deployment to invoke_step()."}

        authorisation_error = self._check_authorisation(capability_id, actor_context)
        if authorisation_error:
            self._record_invocation(capability_id, authorisation_error, actor_context)
            return authorisation_error

        result = self._invoke_with_deployment(cap, deployment, inputs)
        self._record_invocation(capability_id, result, actor_context)
        return result

    def _check_authorisation(self, capability_id: str, actor_context: dict[str, Any] | None) -> dict[str, Any] | None:
        if self._authorisation_port is None or actor_context is None:
            return None
        actor_id = actor_context.get("actor_id")
        actor_type = actor_context.get("actor_type", "agent")
        if not actor_id:
            return None
        result = self._authorisation_port.is_authorised(actor_id, actor_type, capability_id)
        if not result.authorised:
            return {
                "status": "failed",
                "error": f"Execution not authorised: {result.reason}",
                "telemetry": {"authorisation": result.reason},
            }
        return None

    def _record_invocation(self, capability_id: str, result: dict[str, Any], actor_context: dict[str, Any] | None) -> None:
        if self._invocation_recorder is None:
            return
        telemetry = dict(result.get("telemetry", {}))
        if "error" not in telemetry and "error" in result:
            telemetry["error"] = result["error"]
        execution_result = ExecutionResult(
            outputs=result.get("outputs", {}),
            artifacts=result.get("artifacts", []),
            telemetry=telemetry,
        )
        self._invocation_recorder.record_invocation(capability_id, execution_result, actor_context)

    def _invoke_with_deployment(self, cap: Capability, deployment: CapabilityDeployment, inputs: dict[str, Any]) -> dict[str, Any]:
        if deployment.transport == Transport.TIER2_INPROCESS:
            return self._invoke_tier2_deployment(cap, deployment, inputs)
        return self._invoke_tier3_deployment(cap, deployment, inputs)

    def _invoke_tier2_deployment(self, cap: Capability, deployment: CapabilityDeployment, inputs: dict[str, Any]) -> dict[str, Any]:
        if deployment.execution_mode == ExecutionMode.COMPILED and deployment.compiled_ref:
            module_path = deployment.compiled_ref.module_path
            entrypoint = deployment.compiled_ref.entrypoint or "run"
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("_cap_runtime", module_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                fn = getattr(mod, entrypoint)
                result = fn(inputs)
                return {"status": "completed", "outputs": result, "artifacts": [], "telemetry": {}}
            except Exception as exc:  # noqa: BLE001
                return {"status": "failed", "error": str(exc)}
        if deployment.execution_mode == ExecutionMode.AI_MEDIATED and deployment.ai_spec:
            return {
                "status": "completed",
                "outputs": {"composed_prompt": f"[ai_mediated] {deployment.ai_spec.purpose}: {inputs}"},
                "artifacts": [],
                "telemetry": {"mode": "ai_mediated"},
            }
        return {"status": "failed", "error": "no executable implementation"}

    def _invoke_tier3_deployment(self, cap: Capability, deployment: CapabilityDeployment, inputs: dict[str, Any]) -> dict[str, Any]:
        request = CapabilityRequest(
            request_id=f"req-{cap.id}",
            correlation_id=f"corr-{cap.id}",
            capability_id=cap.id,
            capability_name=cap.name,
            inputs=inputs,
            transport=deployment.transport.value,
        )
        if self._bus is not None:
            try:
                self._bus.publish_capability_request("workflow-engine", request.to_json())
            except Exception:
                logger.debug("Failed to publish capability request", exc_info=True)
        reply = CapabilityReply(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="completed",
            outputs={"simulated": True},
            artifacts=[],
            telemetry={"transport": deployment.transport.value},
        )
        return {
            "status": reply.status,
            "correlation_id": reply.correlation_id,
            "request_id": reply.request_id,
            "outputs": reply.outputs,
            "artifacts": reply.artifacts,
            "telemetry": reply.telemetry,
        }
