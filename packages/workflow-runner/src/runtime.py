"""
Pattern Runtime adapter (Phase 3, contract C10 / RUNTIME-MAPPING.md).

Executes pattern steps by invoking Capabilities via the internal agentic API.
Tier 2 (in-process) calls the module's `run(context)` directly; Tier 3 (bus)
publishes a CapabilityRequest to the Event Bus and returns a simulated reply.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from capabilities import Capability, CapabilityRegistry
from bus import CapabilityReply, CapabilityRequest, EventBus


class PatternRuntime:
    """Executes pattern steps as Capability invocations."""

    def __init__(self, registry: Optional[CapabilityRegistry] = None, bus: Optional[EventBus] = None) -> None:
        self._registry = registry or CapabilityRegistry()
        self._bus = bus

    def invoke_step(self, capability_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        cap = self._registry.get(capability_id)
        if cap is None:
            return {"status": "failed", "error": f"Capability not found: {capability_id}"}

        if cap.transport == "tier2_inprocess":
            return self._invoke_tier2(cap, inputs)
        return self._invoke_tier3(cap, inputs)

    def _invoke_tier2(self, cap: Capability, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if cap.execution_mode == "compiled" and cap.compiled_ref:
            module_path = cap.compiled_ref.module_path
            entrypoint = cap.compiled_ref.entrypoint or "run"
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("_cap_runtime", module_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                fn = getattr(mod, entrypoint)
                result = fn(inputs)
                return {"status": "completed", "outputs": result, "artifacts": [], "telemetry": {}}
            except Exception as exc:
                return {"status": "failed", "error": str(exc)}
        if cap.execution_mode == "ai_mediated" and cap.ai_spec:
            return {
                "status": "completed",
                "outputs": {"composed_prompt": f"[ai_mediated] {cap.ai_spec.purpose}: {inputs}"},
                "artifacts": [],
                "telemetry": {"mode": "ai_mediated"},
            }
        return {"status": "failed", "error": "no executable implementation"}

    def _invoke_tier3(self, cap: Capability, inputs: Dict[str, Any]) -> Dict[str, Any]:
        request = CapabilityRequest(
            request_id=f"req-{cap.id}",
            correlation_id=f"corr-{cap.id}",
            capability_id=cap.id,
            capability_name=cap.name,
            inputs=inputs,
            transport="tier3_bus",
        )
        if self._bus is not None:
            try:
                self._bus.publish_capability_request("workflow-engine", request.to_json())
            except Exception:
                pass
        reply = CapabilityReply(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="completed",
            outputs={"simulated": True},
            artifacts=[],
            telemetry={"transport": "tier3_bus"},
        )
        return {
            "status": reply.status,
            "correlation_id": reply.correlation_id,
            "request_id": reply.request_id,
            "outputs": reply.outputs,
            "artifacts": reply.artifacts,
            "telemetry": reply.telemetry,
        }


_default_runtime = PatternRuntime()


def invoke_step(capability_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    return _default_runtime.invoke_step(capability_id, inputs)
