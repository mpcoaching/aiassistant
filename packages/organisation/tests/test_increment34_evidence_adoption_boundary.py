"""
Architectural tests for Increment 34 — Evidence → Workflow Adoption Boundary.

Proves that:
- Evidence (InvocationRecorder, CapabilityProficiency, Work.outcome, MaturationHistory)
  does NOT automatically become a WorkflowDefinition.
- Successful capability execution does NOT automatically become a WorkflowDefinition.
- Workflow adoption is an organisational decision, NOT a WorkflowRunner decision.
- WorkflowRunner remains execution/storage infrastructure only.
- WorkflowDefinition remains the explicit, reusable pattern — with no provenance fields.
- Workflow lookup/discoverability (filesystem YAML search) does NOT confer organisational adoption.
- Skill remains distinct from WorkflowDefinition.
- Capability remains distinct from WorkflowDefinition.
- BAU execution remains distinct from organisational workflow adoption.
- No "compile", "adopt", or "synthesize" operation exists anywhere in the adoption chain.
"""

from __future__ import annotations

import importlib
import inspect
import os
from typing import Any
from unittest.mock import MagicMock

from capability import Capability, CapabilityKind, CapabilityStatus
from capability_proficiency import CapabilityProficiency, ProficiencyLevel
from contracts.capability_execution import CapabilityExecutionPort, ExecutionResult
from contracts.workflow_execution import (
    WorkflowExecutionPort,
    WorkflowExecutionRequest,
    WorkflowExecutionResult,
)
from models import Step, StepType, WorkflowDefinition, WorkflowState

from execution_path import ExecutionPath
from role import Work

PEOPLE_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "people_capability", "src"
))
WORKFLOW_RUNNER_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner", "src"
))
ORGANISATION_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), ".."
))
CAPABILITY_REGISTRY_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "capability_registry", "src"
))
WORKFLOW_RUNNER_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner"
))

# ---- A. Evidence sources and semantics ----


def test_invocation_recorder_records_telemetry_not_workflow_creation() -> None:
    """InvocationRecorder.record_invocation writes capability telemetry to ConceptStore.
    It does NOT create or imply a WorkflowDefinition — it records capability invocation
    outcome (success/failure), not pattern adoption."""
    store = MagicMock()
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )
    from workflow_runner.src.adapters.invocation_recorder_adapter import (
        InvocationRecorderAdapter,
    )

    assessor = CapabilityOutcomeAssessorAdapter()
    recorder = InvocationRecorderAdapter(store=store, outcome_assessor=assessor)

    result = ExecutionResult(
        outputs={"result": "ok"},
        telemetry={"capability_id": "cap-1"},
    )
    recorder.record_invocation("cap-1", result, {"actor_id": "a1"})

    # Evidence recorded to the store
    store.record_invocation.assert_called_once_with("cap-1", "success")
    # The store does NOT receive any WorkflowDefinition creation
    assert not store.method_calls or "create_workflow" not in [
        str(call) for call in store.method_calls
    ]


def test_capability_proficiency_evidence_links_to_work_not_workflow() -> None:
    """CapabilityProficiency evidence entries carry source_work_id — linking
    successful capability exercise back to the originating Work instance.
    This is capability-level proficiency, not workflow pattern adoption."""
    proficiency = CapabilityProficiency(
        id="prof-1",
        capability_id="cap-1",
        actor_id="actor-1",
        proficiency_level=ProficiencyLevel.COMPETENT,
        evidence=[
            {
                "source_work_id": "w-1",
                "type": "execution",
                "content": {"status": "completed", "outputs": {"result": "ok"}},
                "strength": 1.0,
            }
        ],
    )
    # Evidence links to Work, not to a WorkflowDefinition
    assert proficiency.evidence[0]["source_work_id"] == "w-1"
    proficiency_fields = set(CapabilityProficiency.model_fields.keys())
    assert "workflow_id" not in proficiency_fields
    assert "workflow_definition" not in proficiency_fields
    assert "steps" not in proficiency_fields


def test_successful_work_outcome_records_acceptance_not_adoption() -> None:
    """assess_work_outcome checks Work.acceptance_criteria against execution result.
    A 'accepted' result proves this work met its criteria — NOT that an execution
    pattern should become an adopted workflow."""
    from organisation.src.outcome import assess_work_outcome

    work = Work(
        id="w-1",
        title="Task",
        accountable_role_id="r-1",
        acceptance_criteria=["Works correctly"],
    )
    result = {"status": "completed", "outputs": {"summary": "Works correctly"}}
    assessment = assess_work_outcome(work, result)
    assert assessment["accepted"] is True

    # The assessment result contains no workflow-definition field
    assert "workflow_definition" not in assessment
    assert "workflow_id" not in assessment


def test_record_work_learning_records_solved_approach_not_workflow() -> None:
    """record_work_learning writes a SOLVED_APPROACH EnterpriseConcept to EIMS
    for project/initiative work. This documents what worked — NOT that an
    execution pattern has been adopted as a reusable workflow."""
    from concepts import ConceptKind, ConceptStore
    from organisation.src.outcome import assess_work_outcome, record_work_learning

    store = ConceptStore(data_dir="/tmp/test_concepts_incr34")

    work = Work(
        id="w-proj-1",
        title="Build feature",
        work_type="project",
        accountable_role_id="r-1",
        acceptance_criteria=["Works correctly"],
    )
    result = {"status": "completed", "outputs": {"summary": "Works correctly"}}
    assessment = assess_work_outcome(work, result)
    concept = record_work_learning(work, assessment, store)

    if concept is not None:
        assert concept.kind == ConceptKind.SOLVED_APPROACH
        # SOLVED_APPROACH documents the solution, not a workflow pattern
        assert "workflow" not in concept.tags
        assert concept.payload.get("work_id") == work.id


def test_maturation_history_tracks_invocations_not_workflow_adoption() -> None:
    """ConceptStore.record_invocation increments invocation_count/correction_count
    in MaturationHistory. This tracks capability usage statistics — NOT that a
    workflow should be created or adopted."""
    from concepts import ConceptKind, ConceptStore, EnterpriseConcept

    store = ConceptStore(data_dir="/tmp/test_mature_incr34")
    concept = EnterpriseConcept(
        id="cap-1",
        kind=ConceptKind.CAPABILITY,
        name="Analyse data",
    )
    store.upsert(concept)

    # Simulate 10 successful invocations
    for _ in range(10):
        store.record_invocation("cap-1", "success")

    retrieved = store.get("cap-1")
    assert retrieved is not None
    history = retrieved.payload.get("maturation_history", {})
    assert history.get("invocation_count") == 10
    assert history.get("correction_count") == 0
    # High invocation count does NOT create a workflow
    assert not hasattr(store, "create_workflow")
    assert not hasattr(store, "compile_workflow")
    assert not hasattr(store, "adopt_workflow")


# ---- B. Successful execution is not sufficient for workflow adoption ----


def test_repeated_successful_executions_do_not_create_workflow() -> None:
    """Even with many successful capability invocations (maturation), no
    WorkflowDefinition is produced. Frequency alone does not create a workflow."""
    # There is no function anywhere that turns invocation counts into workflows
    # Verify the compiler.py only has compile_skill, not compile_workflow
    from workflow_runner.compiler import compile_skill

    assert callable(compile_skill)
    # No compile_workflow exists
    assert not hasattr(__import__("workflow_runner.compiler", fromlist=["compiler"]), "compile_workflow")


def test_no_pattern_mining_or_extraction_module_exists() -> None:
    """There is no module for pattern mining, workflow extraction, or synthesis."""
    import importlib

    for module_name in [
        "pattern_miner",
        "workflow_synthesizer",
        "workflow_compiler",
        "execution_pattern_miner",
        "evidence_synthesizer",
    ]:
        try:
            importlib.import_module(module_name)
            assert False, f"Module {module_name} should not exist"
        except ImportError:
            pass  # Expected


def test_no_adoption_or_synthesis_function_in_any_module() -> None:
    """No function named 'adopt', 'synthesize', or 'compile_workflow' exists
    in the adoption chain (organisation, workflow_runner, capability_registry)."""
    target_names = {"adopt_workflow", "synthesize_workflow", "compile_workflow",
                    "create_workflow_from_evidence", "workflow_from_capability"}
    # Check key modules
    modules_to_check = [
        "organisation.src.organisation_control_plane",
        "workflow_runner.executor",
        "workflow_runner.loader",
        "workflow_runner.src.operations",
        "workflow_runner.src.worker",
        "workflow_runner.src.composition",
        "workflow_runner.src.adapters.workflow_execution_adapter",
        "workflow_runner.src.adapters.capability_execution_adapter",
        "workflow_runner.runtime",
        "workflow_runner.registry",
        "capability_registry.src.capabilities",
    ]
    for mod_name in modules_to_check:
        try:
            mod = importlib.import_module(mod_name)  # type: ignore[name-defined]
            mod_attrs = set(dir(mod))
            for target in target_names:
                assert target not in mod_attrs, (
                    f"{mod_name} should not have {target}"
                )
        except ImportError:
            pass


# ---- C. Observation from understanding (conceptual boundary) ----


def test_workflow_definition_has_no_understanding_or_evidence_fields() -> None:
    """WorkflowDefinition has no fields for observed evidence, understanding,
    confidence, or source work IDs — it is the *explicit description* produced
    AFTER the organisation understands a pattern, not a container for raw evidence."""
    wf_fields = set(WorkflowDefinition.model_fields.keys())
    # Expected declarative fields
    expected = {"version", "name", "description", "kind", "role", "intent", "inputs", "outputs", "steps"}
    assert expected.issubset(wf_fields)

    # No evidence/understanding fields
    for forbidden in [
        "evidence", "source_work_ids", "source_evidence", "confidence",
        "understanding", "observation", "observed_pattern",
        "rationale", "author", "approved_by", "approved_at",
    ]:
        assert forbidden not in wf_fields, f"WorkflowDefinition should not have {forbidden}"


def test_concept_store_has_no_workflow_creation_api() -> None:
    """ConceptStore (EIMS) records Concepts and invokes, but has no API to
    create or adopt WorkflowDefinitions from evidence."""
    from concepts import ConceptStore

    store_methods = set(dir(ConceptStore))
    assert "upsert" in store_methods
    assert "get" in store_methods
    assert "list_by_kind" in store_methods
    assert "list_by_tag" in store_methods
    assert "record_invocation" in store_methods
    # No workflow creation or adoption
    assert "create_workflow" not in store_methods
    assert "adopt_workflow" not in store_methods
    assert "compile_workflow" not in store_methods
    assert "register_workflow" not in store_methods


# ---- D. Adoption decision boundary ----


def test_ocp_has_no_workflow_creation_or_adoption_method() -> None:
    """OCP can select EXISTING_WORKFLOW (by discovery) but cannot create,
    compile, or adopt a workflow. Adoption authority is separate from
    execution-path selection."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()
    ocp_methods = set(dir(plane))

    # OCP can select execution paths
    assert "select_execution_path" in ocp_methods
    # OCP has NO workflow creation/adoption methods
    for forbidden in [
        "register_workflow", "store_workflow", "compile_workflow",
        "adopt_workflow", "create_workflow", "promote_workflow",
        "synthesize_workflow", "workflow_from_evidence",
    ]:
        assert forbidden not in ocp_methods, f"OCP should not have {forbidden}"


def test_ocp_select_execution_path_only_discovers_existing_workflows() -> None:
    """OCP.select_execution_path only returns EXISTING_WORKFLOW when a workflow
    is already discoverable via workflow_lookup. It never creates or adopts one."""
    plane = _make_inmemory_ocp()

    wf = MagicMock()
    wf.name = "known-pattern"
    wf.description = "a known way of doing things"

    def lookup(intent: str) -> list[Any]:
        if "known" in intent.lower():
            return [wf]
        return []

    result = plane.select_execution_path(
        intent="do the known pattern",
        context={},
        workflow_lookup=lookup,
    )
    assert result.path == ExecutionPath.EXISTING_WORKFLOW
    assert result.workflow is wf
    assert result.capability_id is None

    # Now verify: a capability with many successful invocations is NOT returned as EXISTING_WORKFLOW
    cap = Capability(
        id="cap-1",
        name="Analyse",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(cap)

    def lookup_empty(intent: str) -> list[Any]:
        return []

    result_no_wf = plane.select_execution_path(
        intent="do something new",
        context={"required_capability_ids": ["cap-1"]},
        workflow_lookup=lookup_empty,
        capability_query=lambda cid: MagicMock(available=True, reason="available"),
    )
    assert result_no_wf.path == ExecutionPath.CAPABILITY_PATH
    assert result_no_wf.workflow is None


# ---- E. Minimum adoption contract ----


def test_workflow_execution_request_has_no_adoption_context() -> None:
    """WorkflowExecutionRequest carries only workflow_name and initial_context.
    There is no adoption metadata (reason, author, confidence, source_work_ids)
    in the execution request contract."""
    request_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in request_fields
    assert "initial_context" in request_fields
    # No adoption fields
    for forbidden in [
        "rationale", "author", "approved_by", "confidence",
        "source_work_ids", "adoption_reason", "provenance",
    ]:
        assert forbidden not in request_fields


def test_workflow_execution_result_has_no_adoption_metadata() -> None:
    """WorkflowExecutionResult has only status/workflow_name/output/error.
    No adoption outcome is returned."""
    result_fields = set(WorkflowExecutionResult.model_fields.keys())
    assert "status" in result_fields
    assert "workflow_name" in result_fields
    assert "output" in result_fields
    assert "error" in result_fields
    for forbidden in [
        "adopted", "provenance", "source_work_ids",
        "author", "rationale",
    ]:
        assert forbidden not in result_fields


# ---- F. WorkflowDefinition provenance ----


def test_workflow_definition_has_no_provenance_fields() -> None:
    """WorkflowDefinition has no provenance tracking — no source work IDs,
    no adoption rationale, no author/approver. The only 'version' field is
    a schema version string, not an adoption lineage."""
    wf_fields = set(WorkflowDefinition.model_fields.keys())
    wf = WorkflowDefinition(
        name="test-wf",
        steps=[Step(type=StepType.SKILL, name="s1", uses="skill1")],
    )
    # The version field is a schema version, not an adoption version
    assert hasattr(wf, "version")
    assert isinstance(wf.version, str)
    # No provenance
    assert "provenance" not in wf_fields
    assert "source_work_ids" not in wf_fields
    assert "author" not in wf_fields
    assert "approved_by" not in wf_fields
    assert "rationale" not in wf_fields
    assert "confidence" not in wf_fields
    assert "adopted_at" not in wf_fields


def test_workflow_definition_version_is_schema_not_adoption() -> None:
    """WorkflowDefinition.version is a schema/version identifier (default '1'),
    not a semantic or adoption version. It does not track workflow lineage."""
    wf_fields = set(WorkflowDefinition.model_fields.keys())
    version_field = WorkflowDefinition.model_fields["version"]
    # It's a simple string field with default "1"
    assert version_field.default == "1"
    # No deprecated/deprecation fields for supersession tracking
    for forbidden in [
        "deprecated", "deprecated_at", "superseded_by",
        "replaced_by", "status",
    ]:
        assert forbidden not in wf_fields


# ---- G. Workflow creation/storage boundary ----


def test_workflow_creation_is_filesystem_not_organisational() -> None:
    """WorkflowDefinition is created by writing YAML to the filesystem (via API or
    manually). No organisational port or method is required for the current
    architecture. The file-based mechanism is sufficient as the storage layer."""
    # WorkflowExecutionAdapter loads workflow from filesystem via loader
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )

    adapter = WorkflowExecutionAdapter()
    adapter_methods = set(dir(adapter))
    assert "execute_workflow" in adapter_methods
    # The adapter loads from filesystem, does not create
    adapter_source = inspect.getsource(adapter.__class__)
    assert "load_workflow" in adapter_source or "resolve_workflow_path" in adapter_source
    assert "resolve_workflow_path" in adapter_source


def test_no_workflow_creation_port_in_contracts() -> None:
    """There is no WorkflowCreationPort or WorkflowAdoptionPort in contracts."""
    import importlib

    contract_modules = [
        "contracts.workflow_execution",
        "contracts.capability_execution",
        "contracts.capability_outcome_assessor",
        "contracts.invocation_recorder",
    ]
    for mod_name in contract_modules:
        mod = importlib.import_module(mod_name)
        mod_attrs = set(dir(mod))
        assert "WorkflowCreationPort" not in mod_attrs
        assert "WorkflowAdoptionPort" not in mod_attrs
        assert "WorkflowSynthesisPort" not in mod_attrs


# ---- H. Workflow lookup / discoverability ----


def test_build_workflow_lookup_searches_filesystem_only() -> None:
    """build_workflow_lookup searches YAML files by name/description keywords.
    It does NOT consult organisational adoption status — discovery is purely
    filesystem-based."""
    from workflow_runner.src.composition import build_workflow_lookup

    source_code = inspect.getsource(build_workflow_lookup)

    # It loads from YAML files
    assert "load_workflow" in source_code
    assert "glob" in source_code
    # It matches by name/description keywords
    assert "intent_lower" in source_code or "intent" in source_code
    # It does NOT check adoption status
    assert "adoption" not in source_code.lower()
    assert "adopted" not in source_code.lower()


def test_workflow_lookup_matches_by_name_not_adoption_status() -> None:
    """OCP uses workflow_lookup (which searches filesystem) to discover workflows.
    A workflow on the filesystem is discoverable — but filesystem presence does
    NOT equal organisational adoption (there is no adoption status to check)."""
    from workflow_runner.src.composition import build_workflow_lookup

    lookup = build_workflow_lookup()
    # Calling lookup returns whatever matches by name/description keywords
    # It has no concept of "adopted" vs "draft" or "proposed" workflows
    result = lookup("nonexistent-workflow-name-12345")
    assert isinstance(result, list)


def test_workflow_loader_loads_yaml_not_adopts_from_evidence() -> None:
    """load_workflow reads and validates YAML. It does not synthesize from
    capability invocation evidence or Work outcomes."""
    from loader import load_workflow

    source_code = inspect.getsource(load_workflow)
    # It reads YAML and validates structure
    assert "yaml" in source_code
    assert "WorkflowDefinition" in source_code
    # It does not synthesize from evidence
    assert "record_invocation" not in source_code
    assert "MaturationHistory" not in source_code
    assert "invoke" not in source_code.lower()


# ---- I. Capability ↔ Workflow relationship ----


def test_workflow_definition_has_no_capability_id() -> None:
    """WorkflowDefinition does not carry a capability_id — it is a pattern that
    may orchestrate multiple capabilities/skills. OCP matches workflows by name,
    not by capability association."""
    wf_fields = set(WorkflowDefinition.model_fields.keys())
    assert "capability_id" not in wf_fields
    assert "capability_ids" not in wf_fields
    assert "required_capability_ids" not in wf_fields


def test_ocp_does_not_associate_workflows_with_capabilities() -> None:
    """OCP.select_execution_path does not associate workflows with capabilities.
    The workflow_lookup callback matches by intent (name/description keywords),
    not by capability_id. This is a gap: organisational metadata to associate
    a workflow with capabilities does not exist yet."""
    source_code = inspect.getsource(
        __import__("organisation_control_plane", fromlist=["InMemoryOrganisationControlPlane"])
        .InMemoryOrganisationControlPlane.select_execution_path
    )
    # The OCP workflow lookup uses 'intent' string matching, not capability association
    assert "workflow_lookup(intent)" in source_code or "workflow_lookup(" in source_code
    # No capability-to-workflow association method exists
    assert "associate_workflow_capability" not in source_code
    assert "workflow_capability" not in source_code


# ---- J. Skill ↔ Workflow relationship ----


def test_skill_has_no_workflow_steps() -> None:
    """A Skill is a learned method — it has no step structure. It does not
    become a WorkflowDefinition simply because it is executed successfully."""
    from skill import Skill

    Skill(
        id="skill-1",
        capability_id="cap-1",
        name="Scoring method",
        method="Weighted scoring against ICP",
    )
    skill_fields = set(Skill.model_fields.keys())
    assert "steps" not in skill_fields
    assert "steps" in set(WorkflowDefinition.model_fields.keys())


def test_capability_registry_has_no_workflow_methods() -> None:
    """CapabilityRegistry handles capability registration/promotion — not
    workflow creation. Capability promotion (via CapabilityStatus) does NOT
    create a WorkflowDefinition."""
    from capability_registry.src.capabilities import CapabilityRegistry

    registry_methods = set(dir(CapabilityRegistry))
    assert "register" in registry_methods
    assert "get" in registry_methods
    assert "promote" in registry_methods
    # No workflow methods
    for forbidden in [
        "create_workflow", "register_workflow", "compile_workflow",
        "adopt_workflow", "synthesize_workflow",
    ]:
        assert forbidden not in registry_methods


# ---- K. BAU transition ----


def test_bau_work_execution_does_not_create_workflow() -> None:
    """BAU Work is executed via CAPABILITY_PATH or EXISTING_WORKFLOW. The
    execution itself (Worker, Operations, backends) does not create
    WorkflowDefinitions from successful BAU execution."""
    from workflow_runner.src.operations import Operations

    ops_methods = set(dir(Operations))
    # Operations reports results to org plane
    assert "_handle_event" in ops_methods
    assert "_select_backend" in ops_methods
    # Operations does NOT create workflows
    for forbidden in [
        "create_workflow", "compile_workflow", "adopt_workflow",
        "synthesize_workflow", "register_workflow",
    ]:
        assert forbidden not in ops_methods


def test_workflow_execution_does_not_trigger_evidence_to_adoption() -> None:
    """Executing a WorkflowDefinition (via WorkflowExecutionPort) produces
    WorkState/WorkflowState and execution results — NOT an adoption decision.
    The execution path and the adoption path are separate."""
    # WorkflowExecutionPort.execute_workflow signature
    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = list(sig.parameters.keys())
    assert "request" in params
    # No adoption parameter
    assert "adopt" not in params
    assert "publish" not in params


# ---- L. Failure feedback ----


def test_failed_work_outcome_is_evidence_not_automatic_revision() -> None:
    """A failed workflow execution records Work.outcome — this is evidence
    available for organisational learning. It does NOT automatically
    modify the WorkflowDefinition."""
    from organisation.src.outcome import assess_work_outcome

    work = Work(
        id="w-fail",
        title="Task",
        accountable_role_id="r-1",
        acceptance_criteria=["Should work"],
    )
    result = {
        "status": "failed",
        "outputs": {"error": "Capability failed on edge case"},
    }
    assessment = assess_work_outcome(work, result)
    assert assessment["accepted"] is False

    # The assessment does NOT trigger workflow revision
    assert "workflow_updated" not in assessment
    assert "workflow_revised" not in assessment


def test_workflow_state_has_no_failure_feedback_to_definition() -> None:
    """WorkflowState records execution failures (status='failed', error=...).
    But WorkflowState and WorkflowDefinition are separate — a failure in
    execution does NOT modify the definition."""
    state = WorkflowState(
        workflow_id="wf-1",
        workflow_name="test",
        workflow_path="/tmp/test.yaml",
        steps=[Step(type=StepType.SKILL, name="s1", uses="s1")],
    )
    state.status = "failed"
    state.error = "Step failed during execution"

    # WorkflowState and WorkflowDefinition are separate objects
    assert type(state).__name__ != "WorkflowDefinition"
    # WorkflowState has no method to update a workflow definition
    state_fields = set(WorkflowState.model_fields.keys())
    assert "definition" not in state_fields
    assert "workflow_definition" not in state_fields


# ---- M. Versioning / supersession ----


def test_workflow_definition_has_no_deprecation_or_supersession() -> None:
    """WorkflowDefinition has no status, deprecation, or supersession fields.
    There is no mechanism to mark a workflow as deprecated or superseded."""
    wf_fields = set(WorkflowDefinition.model_fields.keys())
    for forbidden in [
        "status", "deprecated", "deprecated_at",
        "superseded_by", "replaced_by", "retired",
    ]:
        assert forbidden not in wf_fields


def test_workflow_definition_version_field_does_not_track_adoption_lineage() -> None:
    """WorkflowDefinition.version is a schema version (default '1') used by
    the loader for future format upgrades. It does NOT track adoption,
    lineage, or supersession of the execution pattern."""
    wf = WorkflowDefinition(
        name="test",
        version="1",
        steps=[Step(type=StepType.SKILL, name="s1", uses="s1")],
    )
    assert wf.version == "1"
    # It's not a list of versions or adoptions
    assert isinstance(wf.version, str)


# ---- N. Architectural tests: Evidence → WorkflowDefinition boundary ----


def test_invocation_recorder_does_not_create_workflow_definition() -> None:
    """Direct test: calling record_invocation never results in a WorkflowDefinition
    being created anywhere. The ConceptStore has no method to create workflows."""
    from concepts import ConceptStore

    store = ConceptStore(data_dir="/tmp/test_no_wf_incr34")

    # Check that ConceptStore source has no workflow creation
    store_source = inspect.getsource(ConceptStore)
    assert "workflowdefinition" not in store_source.lower()
    # More precisely: no method creates a WorkflowDefinition
    for method_name in dir(store):
        method = getattr(store, method_name)
        if callable(method) and not method_name.startswith("_"):
            method_source = inspect.getsource(method).lower()
            assert "workflowdefinition" not in method_source
            assert "workflow_definition" not in method_source


def test_no_synthesis_pipeline_from_evidence_to_workflow() -> None:
    """There is no code path that takes evidence (CapabilityProficiency,
    MaturationHistory, Work outcome) and produces a WorkflowDefinition."""
    # Check operations.py for any workflow creation
    ops_source = inspect.getsource(
        __import__("workflow_runner.src.operations", fromlist=["operations"])
    )
    assert "WorkflowDefinition" not in ops_source
    # Check worker.py
    worker_source = inspect.getsource(
        importlib.import_module("workflow_runner.src.worker")
    )
    assert "WorkflowDefinition(" not in worker_source

    # Check the OCP source
    ocp_source = inspect.getsource(
        __import__("organisation_control_plane", fromlist=["organisation_control_plane"])
    )
    assert "WorkflowDefinition(" not in ocp_source


def test_workflow_execution_adapter_has_no_adoption_methods() -> None:
    """WorkflowExecutionAdapter only has execute_workflow — no adoption or
    creation methods."""
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )

    adapter = WorkflowExecutionAdapter()
    adapter_methods = set(dir(adapter))
    assert "execute_workflow" in adapter_methods
    for forbidden in [
        "adopt", "create_workflow", "compile_workflow",
        "register_workflow", "promote_workflow", "synthesize",
    ]:
        matching = [m for m in adapter_methods if forbidden in m.lower()]
        assert not matching, f"Adapter should not have methods containing '{forbidden}'"


# ---- O. Capability/CapabilityExecutionPort isolation ----


def test_capability_execution_port_signature_has_no_workflow() -> None:
    """CapabilityExecutionPort.execute takes only capability_id, context, actor_context.
    It does not accept or return workflow-related information."""
    sig = inspect.signature(CapabilityExecutionPort.execute)
    params = list(sig.parameters.keys())
    assert "capability_id" in params
    assert "context" in params
    assert "actor_context" in params
    assert "workflow_id" not in params
    assert "workflow_name" not in params


def test_execution_result_does_not_contain_workflow_info() -> None:
    """ExecutionResult (from CapabilityExecutionPort) has no workflow fields."""
    result_fields = set(ExecutionResult.model_fields.keys())
    assert "outputs" in result_fields
    assert "artifacts" in result_fields
    assert "telemetry" in result_fields
    for forbidden in [
        "workflow_id", "workflow_name", "workflow_path",
        "workflow_definition",
    ]:
        assert forbidden not in result_fields


# ---- P. WorkflowLookup / OCP discovery vs adoption ----


def test_workflow_lookup_callback_is_discovery_not_adoption() -> None:
    """The workflow_lookup callback passed to OCP.select_execution_path is a
    discovery mechanism (searches filesystem). It does NOT represent
    organisational adoption — it merely finds what exists on disk."""
    from workflow_runner.src.composition import build_workflow_lookup

    lookup = build_workflow_lookup()
    lookup_code = inspect.getsource(lookup)
    # The lookup function returns loaded WorkflowDefinitions from YAML
    assert "load_workflow" in lookup_code or "yaml" in lookup_code
    # It is not an adoption check
    assert "adopt" not in lookup_code.lower()


def test_organisation_paperclip_backend_separate_from_workflow_adoption() -> None:
    """PaperclipBackend implements ExecutionBackend (execute/can_handle).
    It does not decide workflow adoption."""
    from workflow_runner.src.operations import PaperclipBackend

    backend = PaperclipBackend(MagicMock())
    backend_methods = [m for m in dir(backend) if not m.startswith("_")]
    assert "execute" in backend_methods
    assert "can_handle" in backend_methods
    for forbidden in ["adopt", "compile_workflow", "register_workflow", "create_workflow"]:
        matching = [m for m in backend_methods if forbidden in m.lower()]
        assert not matching


# ---- Helpers ----


def _make_inmemory_ocp() -> Any:
    """Create an InMemoryOrganisationControlPlane for testing."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    return InMemoryOrganisationControlPlane()
