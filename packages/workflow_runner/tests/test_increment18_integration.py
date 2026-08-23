"""
Integration tests for Increment 18 — invocation telemetry recording.

Proves:
  PatternRuntime.invoke_step() records invocation on success
  PatternRuntime.invoke_step() records invocation on failure (authorisation)
  CapabilityExecutionAdapter.execute() records invocation on success
  CapabilityExecutionAdapter.execute() records invocation on authorisation failure
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

_packages_root = Path(__file__).resolve().parent.parent.parent
for _pkg in ["bus", "capability_registry", "ai", "workflow_runner", "langgraph"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

_wf_src = str(_packages_root / "workflow_runner" / "src")
if _wf_src in sys.path:
    sys.path.remove(_wf_src)
sys.path.insert(0, _wf_src)

from capabilities import CapabilityRegistry
from capability import Capability, CapabilityKind
from capability_registry.src.adapters.execution_authorisation_adapter import (
    InMemoryExecutionAuthorisationPort,
)
from capability_registry.src.concept_store_adapter import ConceptStoreCapabilityRepository
from concepts import ConceptStore
from contracts.capability_execution import ExecutionResult

from capability_deployment import (
    AiSpec,
    CapabilityDeployment,
    CompiledRef,
    ExecutionMode,
    Transport,
)
from deployment_resolver import DeploymentResolver
from runtime import PatternRuntime
from workflow_runner.src.adapters.invocation_recorder_adapter import InvocationRecorderAdapter


def _setup_registry(tmp_path: Path) -> tuple[CapabilityRegistry, Capability]:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(ConceptStoreCapabilityRepository(store))
    cap = Capability(
        id="cap-integ",
        name="integration_cap",
        capability_kind=CapabilityKind.TOOL,
        interface={
            "inputs": [{"name": "x", "type": "string", "required": True}],
            "outputs": [{"name": "result", "type": "string"}],
            "errors": [],
        },
    )
    reg.register(cap)
    return reg, cap


def test_pattern_runtime_records_invocation_on_success(tmp_path: Path) -> None:
    reg, cap = _setup_registry(tmp_path)
    deployment = CapabilityDeployment(
        capability_id=cap.id,
        environment="test",
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport=Transport.TIER2_INPROCESS,
        ai_spec=AiSpec(purpose="test purpose"),
    )
    resolver = DeploymentResolver([deployment])
    store = ConceptStore(data_dir=str(tmp_path))
    recorder = InvocationRecorderAdapter(store=store)
    runtime = PatternRuntime(registry=reg, invocation_recorder=recorder)

    reply = runtime.invoke_step(
        cap.id,
        {"x": "1"},
        deployment=resolver.resolve(cap.id, "test"),
    )

    assert reply["status"] == "completed"
    concept = store.get(cap.id)
    assert concept is not None
    history = concept.payload.get("maturation_history", {})
    assert history.get("invocation_count") == 1


def test_pattern_runtime_records_invocation_on_authorisation_failure(tmp_path: Path) -> None:
    reg, cap = _setup_registry(tmp_path)
    deployment = CapabilityDeployment(
        capability_id=cap.id,
        environment="test",
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport=Transport.TIER2_INPROCESS,
        ai_spec=AiSpec(purpose="test purpose"),
    )
    resolver = DeploymentResolver([deployment])
    store = ConceptStore(data_dir=str(tmp_path))
    recorder = InvocationRecorderAdapter(store=store)
    authorisation_port = InMemoryExecutionAuthorisationPort()
    runtime = PatternRuntime(
        registry=reg,
        authorisation_port=authorisation_port,
        invocation_recorder=recorder,
    )

    reply = runtime.invoke_step(
        cap.id,
        {"x": "1"},
        deployment=resolver.resolve(cap.id, "test"),
        actor_context={"actor_id": "agent-unknown", "actor_type": "agent"},
    )

    assert reply["status"] == "failed"
    concept = store.get(cap.id)
    assert concept is not None
    history = concept.payload.get("maturation_history", {})
    assert history.get("invocation_count") == 1
    assert history.get("correction_count") == 1


def test_capability_execution_adapter_records_invocation_on_success(tmp_path: Path) -> None:
    reg, cap = _setup_registry(tmp_path)
    deployment = CapabilityDeployment(
        capability_id=cap.id,
        environment="test",
        execution_mode=ExecutionMode.COMPILED,
        transport=Transport.TIER2_INPROCESS,
        compiled_ref=CompiledRef(module_path="tests.dummy_module", entrypoint="run"),
    )
    resolver = DeploymentResolver([deployment])
    store = ConceptStore(data_dir=str(tmp_path))
    recorder = InvocationRecorderAdapter(store=store)

    def deployment_factory(c):
        return resolver.resolve(c.id, "test")

    with patch("workflow_runner.src.adapters.capability_execution_adapter.execute_capability") as mock_exec:
        mock_exec.return_value = ExecutionResult(
            outputs={"result": "ok"},
            artifacts=[],
            telemetry={"capability_id": cap.id},
        )
        from workflow_runner.src.adapters.capability_execution_adapter import (
            CapabilityExecutionAdapter,
        )

        adapter = CapabilityExecutionAdapter(
            registry=reg,
            deployment_factory=deployment_factory,
            invocation_recorder=recorder,
        )

        result = adapter.execute(cap.id, {"x": "1"}, {"actor_id": "agent-1", "actor_type": "agent"})

    assert result.outputs == {"result": "ok"}
    concept = store.get(cap.id)
    assert concept is not None
    history = concept.payload.get("maturation_history", {})
    assert history.get("invocation_count") == 1


def test_capability_execution_adapter_records_invocation_on_authorisation_failure(tmp_path: Path) -> None:
    reg, cap = _setup_registry(tmp_path)
    store = ConceptStore(data_dir=str(tmp_path))
    recorder = InvocationRecorderAdapter(store=store)
    authorisation_port = InMemoryExecutionAuthorisationPort()

    def deployment_factory(c):
        return None

    from workflow_runner.src.adapters.capability_execution_adapter import (
        CapabilityExecutionAdapter,
    )

    adapter = CapabilityExecutionAdapter(
        registry=reg,
        deployment_factory=deployment_factory,
        authorisation_port=authorisation_port,
        invocation_recorder=recorder,
    )

    result = adapter.execute(cap.id, {"x": "1"}, {"actor_id": "agent-1", "actor_type": "agent"})

    assert result.telemetry.get("error") == "execution_not_authorised"
    concept = store.get(cap.id)
    assert concept is not None
    history = concept.payload.get("maturation_history", {})
    assert history.get("invocation_count") == 1
