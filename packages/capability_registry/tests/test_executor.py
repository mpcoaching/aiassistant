"""
Tests for CapabilityExecutor and create_test_artifact (Increment 2).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from capabilities import CapabilityRegistry
from capability import Capability, CapabilityKind
from capability_deployment import CapabilityDeployment, CompiledRef, ExecutionMode, Transport
from capability_registry.src.concept_store_adapter import ConceptStoreCapabilityRepository
from workflow_runner.src.executor import execute_capability
from concepts import ConceptKind, ConceptStore


def _register_create_test_artifact(tmp_path: Path):
    """Register create_test_artifact as a compiled capability."""
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(ConceptStoreCapabilityRepository(store))
    cap = Capability(
        id="cap-create_test_artifact",
        name="create_test_artifact",
        description="Creates a test artifact record",
        owner="core",
        created_by="test",
        tags=["test", "artifact"],
        capability_kind=CapabilityKind.TOOL,
    )
    reg.register(cap)
    deployment = CapabilityDeployment(
        capability_id=cap.id,
        environment="test",
        execution_mode=ExecutionMode.COMPILED,
        transport=Transport.TIER2_INPROCESS,
        compiled_ref=CompiledRef(
            module_path="packages.capabilities.create_test_artifact.run",
            entrypoint="run",
            tests_passed=True,
        ),
    )
    return reg, cap, deployment


def test_execute_capability_success(tmp_path: Path):
    reg, cap, deployment = _register_create_test_artifact(tmp_path)
    context = {"label": "foo", "concept_store_data_dir": str(tmp_path / "concepts_data")}
    result = execute_capability(cap, context, deployment)
    assert result.outputs["label"] == "foo"
    assert result.outputs["artifact_id"].startswith("art-")
    assert result.outputs["kind"] == "solved_approach"
    assert result.telemetry["capability_name"] == "create_test_artifact"


def test_execute_capability_no_deployment():
    cap = Capability(
        id="cap-bad",
        name="bad",
        description="bad",
        owner="core",
        created_by="test",
        capability_kind=CapabilityKind.TOOL,
    )
    with pytest.raises(ValueError, match="execute_capability requires a CapabilityDeployment"):
        execute_capability(cap, {})


def test_execute_capability_missing_compiled_ref():
    cap = Capability(
        id="cap-noref",
        name="noref",
        description="noref",
        owner="core",
        created_by="test",
        capability_kind=CapabilityKind.TOOL,
    )
    deployment = CapabilityDeployment(
        capability_id=cap.id,
        environment="test",
        execution_mode=ExecutionMode.COMPILED,
        transport=Transport.TIER2_INPROCESS,
        compiled_ref=None,
    )
    with pytest.raises(ValueError, match="execute_capability requires compiled_ref in deployment"):
        execute_capability(cap, {}, deployment)


def test_execute_capability_missing_module():
    cap = Capability(
        id="cap-missing",
        name="missing",
        description="missing",
        owner="core",
        created_by="test",
        capability_kind=CapabilityKind.TOOL,
    )
    deployment = CapabilityDeployment(
        capability_id=cap.id,
        environment="test",
        execution_mode=ExecutionMode.COMPILED,
        transport=Transport.TIER2_INPROCESS,
        compiled_ref=CompiledRef(
            module_path="packages.capabilities.nonexistent_module.run",
            entrypoint="run",
            tests_passed=True,
        ),
    )
    with pytest.raises(FileNotFoundError, match="Cannot import capability module"):
        execute_capability(cap, {}, deployment)


def test_create_test_artifact_persists_concept(tmp_path: Path):
    sys_path = str(tmp_path)
    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)

    data_dir = tmp_path / "concepts_data"
    context = {"label": "bar", "concept_store_data_dir": str(data_dir)}
    from packages.capabilities.create_test_artifact.run import run as cap_run
    outputs = cap_run(context)

    store = ConceptStore(data_dir=str(data_dir))
    concept = store.get(outputs["artifact_id"])
    assert concept is not None
    assert concept.name == "bar"
    assert concept.kind == ConceptKind.SOLVED_APPROACH
    assert "create_test_artifact" in concept.tags


def test_create_test_artifact_returns_expected_fields(tmp_path: Path):
    sys_path = str(tmp_path)
    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)

    data_dir = tmp_path / "concepts_data"
    context = {"label": "baz", "concept_store_data_dir": str(data_dir)}
    from packages.capabilities.create_test_artifact.run import run as cap_run
    outputs = cap_run(context)

    assert "artifact_id" in outputs
    assert "created_at" in outputs
    assert "label" in outputs
    assert "kind" in outputs
    assert outputs["label"] == "baz"
    assert outputs["kind"] == "solved_approach"


def test_invocation_recording_through_registry(tmp_path: Path):
    reg, cap, deployment = _register_create_test_artifact(tmp_path)
    context = {"label": "qux", "concept_store_data_dir": str(tmp_path / "concepts_data")}
    execute_capability(cap, context, deployment)
