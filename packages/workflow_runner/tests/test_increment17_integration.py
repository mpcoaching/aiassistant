"""
Integration tests for Increment 17 — deployment resolution + authorisation enforcement.

Proves:
  resolve deployment -> authorise actor -> execute
  resolve deployment -> reject unauthorised actor -> execution NOT called
  missing deployment -> execution NOT called
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_packages_root = Path(__file__).resolve().parent.parent.parent
for _pkg in ["bus", "capability_registry", "ai", "workflow_runner", "langgraph"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

from capabilities import CapabilityRegistry
from capability import Capability, CapabilityKind
from capability_assignment import CapabilityAssignment
from capability_registry.src.adapters.execution_authorisation_adapter import (
    InMemoryExecutionAuthorisationPort,
)
from capability_registry.src.concept_store_adapter import ConceptStoreCapabilityRepository
from concepts import ConceptStore

from capability_deployment import AiSpec, CapabilityDeployment, ExecutionMode, Transport
from deployment_resolver import DeploymentNotFoundError, DeploymentResolver
from runtime import PatternRuntime


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


def test_authorised_execution_succeeds(tmp_path: Path) -> None:
    reg, cap = _setup_registry(tmp_path)
    deployment = CapabilityDeployment(
        capability_id=cap.id,
        environment="test",
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport=Transport.TIER2_INPROCESS,
        ai_spec=AiSpec(purpose="test purpose"),
    )
    resolver = DeploymentResolver([deployment])
    authorisation_port = InMemoryExecutionAuthorisationPort(
        assignments=[
            CapabilityAssignment(
                id="asgn-1",
                capability_id=cap.id,
                assignee_type="agent",
                assignee_id="agent-1",
            )
        ],
    )
    runtime = PatternRuntime(registry=reg, authorisation_port=authorisation_port)
    reply = runtime.invoke_step(
        cap.id,
        {"x": "1"},
        deployment=resolver.resolve(cap.id, "test"),
        actor_context={"actor_id": "agent-1", "actor_type": "agent"},
    )
    assert reply["status"] == "completed"


def test_unauthorised_actor_is_rejected(tmp_path: Path) -> None:
    reg, cap = _setup_registry(tmp_path)
    deployment = CapabilityDeployment(
        capability_id=cap.id,
        environment="test",
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport=Transport.TIER2_INPROCESS,
        ai_spec=AiSpec(purpose="test purpose"),
    )
    resolver = DeploymentResolver([deployment])
    authorisation_port = InMemoryExecutionAuthorisationPort()
    runtime = PatternRuntime(registry=reg, authorisation_port=authorisation_port)
    reply = runtime.invoke_step(
        cap.id,
        {"x": "1"},
        deployment=resolver.resolve(cap.id, "test"),
        actor_context={"actor_id": "agent-unknown", "actor_type": "agent"},
    )
    assert reply["status"] == "failed"
    assert "not authorised" in reply.get("error", "").lower()


def test_missing_deployment_prevents_execution(tmp_path: Path) -> None:
    reg, cap = _setup_registry(tmp_path)
    resolver = DeploymentResolver()
    with pytest.raises(DeploymentNotFoundError):
        deployment = resolver.resolve(cap.id, "test")
        runtime = PatternRuntime(registry=reg)
        runtime.invoke_step(cap.id, {"x": "1"}, deployment=deployment)
