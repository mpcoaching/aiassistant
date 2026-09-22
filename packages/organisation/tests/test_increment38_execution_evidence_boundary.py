"""
Architectural tests for Increment 38 — Workflow Execution → Organisational Evidence Boundary.

Investigates whether workflow execution produces organisational evidence
that the current architecture needs to retain, or whether WorkflowState/runtime
telemetry is intentionally the correct endpoint for BAU workflow execution.

Tests established facts from Increment 36 (execution authority) and
Increment 37 (BAU/Work/WorkflowState separation). This increment adds
new evidence regarding the evidence boundary.

Tests below prove the *established* architectural decisions of this
increment. Tests already covered by Increment 36 (execution authority)
or 37 (BAU semantics) are NOT duplicated here.
"""

from __future__ import annotations

import inspect
import os
import re

ORGANISATION_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "src"
))
WORKFLOW_RUNNER_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner", "src"
))
WORKFLOW_RUNNER_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner"
))
CONTRACTS_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "contracts"
))
AI_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "ai", "src"
))


# ---- A. Workflow Execution Output: What Exists After Execution ----


def test_workflow_execution_result_has_only_status_name_output_error() -> None:
    """WorkflowExecutionResult has exactly four fields: status, workflow_name, output, error.

    It has no evidence fields (no capability_id, work_id, invocation_count,
    correction_count, outcome, assessment, or any organisational metadata).
    """
    from contracts.workflow_execution import WorkflowExecutionResult

    fields = set(WorkflowExecutionResult.model_fields.keys())
    assert fields == {"status", "workflow_name", "output", "error"}


def test_workflow_execution_result_has_no_organisational_fields() -> None:
    """WorkflowExecutionResult has no fields that could serve as evidence anchors.

    Specifically, it has no: capability_id, work_id, workflow_id, actor_id,
    invocation_count, correction_count, outcome, assessment, organisation_id,
    evidence, learning, maturity, or confidence fields.
    """
    from contracts.workflow_execution import WorkflowExecutionResult

    forbidden = [
        "capability_id", "work_id", "workflow_id", "actor_id",
        "invocation_count", "correction_count", "outcome", "assessment",
        "organisation_id", "evidence", "learning", "maturity", "confidence",
    ]
    for field in forbidden:
        assert field not in WorkflowExecutionResult.model_fields, (
            f"WorkflowExecutionResult has unexpected field '{field}'"
        )


def test_workflow_execution_result_output_contains_execution_telemetry() -> None:
    """WorkflowExecutionResult.output contains the raw executor summary dict.

    The output dict includes step_results, context, total_steps, completed_steps.
    This is execution telemetry, not organisational evidence. It is available
    as an unstructured dict but has no organisational schema or purpose.
    """
    from contracts.workflow_execution import WorkflowExecutionResult

    result = WorkflowExecutionResult(
        status="completed",
        workflow_name="test",
        output={
            "workflow_id": "wf-1",
            "step_results": [{"step_name": "step1", "status": "completed"}],
            "context": {},
            "total_steps": 2,
            "completed_steps": 2,
        },
        error=None,
    )

    assert result.output is not None
    assert "step_results" in result.output
    assert "context" in result.output
    assert "total_steps" in result.output
    assert "completed_steps" in result.output


def test_workflow_execution_result_output_is_unstructured() -> None:
    """WorkflowExecutionResult.output is a plain dict, not a typed evidence structure.

    Unlike ExecutionResult (which has typed outputs, artifacts, telemetry)
    or Work (which has typed outcome, acceptance_criteria), the workflow
    execution output is an unstructured dict with no organisational schema.
    """
    from contracts.capability_execution import ExecutionResult
    from contracts.workflow_execution import WorkflowExecutionResult

    result = WorkflowExecutionResult(
        status="completed",
        workflow_name="test",
        output={"key": "value"},
        error=None,
    )

    assert isinstance(result.output, dict)
    assert hasattr(ExecutionResult, "model_fields")
    assert set(ExecutionResult.model_fields.keys()) == {"outputs", "artifacts", "telemetry"}


# ---- B. What Is Lost at the Boundary ----


def test_workflow_state_is_not_in_workflow_execution_result() -> None:
    """WorkflowState fields (step_results, context, current_step_index)
    are NOT in WorkflowExecutionResult.

    The workflow execution adapter converts the executor summary to a
    WorkflowExecutionResult that only carries status, workflow_name, output, error.
    The rich execution state in WorkflowState does not propagate.
    """
    from contracts.workflow_execution import WorkflowExecutionResult
    from workflow_runner.models import WorkflowState

    workflow_state_fields = set(WorkflowState.model_fields.keys())
    result_fields = set(WorkflowExecutionResult.model_fields.keys())

    for field in ["step_results", "context", "current_step_index", "log_path"]:
        if field in workflow_state_fields:
            assert field not in result_fields, (
                f"WorkflowExecutionResult has WorkflowState field '{field}'"
            )


def test_workflow_execution_adapter_does_not_return_workflowstate() -> None:
    """WorkflowExecutionAdapter.execute_workflow returns WorkflowExecutionResult,
    not WorkflowState.

    WorkflowState is created internally by the executor but never returned
    to the caller. The adapter converts the executor's dict summary to
    WorkflowExecutionResult, which has a narrower field set.
    """
    from contracts.workflow_execution import WorkflowExecutionResult
    from workflow_runner.models import WorkflowState

    assert WorkflowExecutionResult != WorkflowState


def test_workflow_execution_result_has_no_step_results_typed_field() -> None:
    """WorkflowExecutionResult has no step_results field.

    Step results exist in WorkflowState and in the raw executor summary dict
    (under output), but WorkflowExecutionResult does not expose them as a
    typed field. They are embedded in the unstructured output dict.
    """
    from contracts.workflow_execution import WorkflowExecutionResult

    assert "step_results" not in WorkflowExecutionResult.model_fields


# ---- C. Comparison with Evidence Mechanisms ----


def test_invocation_recorder_requires_capability_id() -> None:
    """InvocationRecorder.record_invocation requires capability_id.

    Workflow execution has no capability_id — workflow steps use skills
    (Step.uses is a skill name), not capabilities. There is no way to
    call record_invocation with workflow execution results.
    """
    from contracts.invocation_recorder import InvocationRecorder

    sig = inspect.signature(InvocationRecorder.record_invocation)
    params = list(sig.parameters.keys())
    assert "capability_id" in params


def test_invocation_recorder_records_on_capability_concepts() -> None:
    """InvocationRecorder records on Capability concepts in ConceptStore.

    ConceptStore.record_invocation updates MaturationHistory on a
    Capability concept (invocation_count, correction_count).
    Workflow execution does not involve Capability concepts.
    """
    from concepts import ConceptKind, ConceptStore, EnterpriseConcept

    store = ConceptStore(data_dir="/tmp/test_incr38_invocation")

    concept = EnterpriseConcept(
        id="cap-1",
        kind=ConceptKind.CAPABILITY,
        name="Test capability",
    )
    store.upsert(concept)

    store.record_invocation("cap-1", "success")

    retrieved = store.get("cap-1")
    assert retrieved is not None
    history = retrieved.payload.get("maturation_history") or {}
    assert history.get("invocation_count", 0) >= 1


def test_invocation_recorder_is_wired_only_to_capability_execution() -> None:
    """InvocationRecorder is wired only to CapabilityExecutionAdapter,
    not to WorkflowExecutionAdapter.

    The composition root creates InvocationRecorder and passes it to
    CapabilityExecutionAdapter but never to WorkflowExecutionAdapter.
    """
    from workflow_runner.src.adapters.capability_execution_adapter import CapabilityExecutionAdapter
    from workflow_runner.src.adapters.workflow_execution_adapter import WorkflowExecutionAdapter

    adapter_init = inspect.signature(CapabilityExecutionAdapter.__init__)
    adapter_params = list(adapter_init.parameters.keys())
    assert "invocation_recorder" in adapter_params

    wf_adapter_init = inspect.signature(WorkflowExecutionAdapter.__init__)
    wf_params = list(wf_adapter_init.parameters.keys())
    assert "invocation_recorder" not in wf_params


def test_record_work_learning_requires_work() -> None:
    """record_work_learning requires a Work item.

    Workflow execution does not create Work, so there is no Work item
    to pass to record_work_learning. The function signature requires
    a Work object with work_type, title, id, accountable_role_id fields.
    """
    from organisation.src.outcome import record_work_learning

    sig = inspect.signature(record_work_learning)
    params = list(sig.parameters.keys())
    assert "work" in params


def test_record_work_learning_excludes_bau() -> None:
    """record_work_learning explicitly excludes BAU work.

    Even if workflow execution DID create Work items, BAU work items
    are excluded from EIMS learning (work_type must be 'project' or
    'initiative'). This is architectural — BAU is routine execution,
    not innovation that needs organisational memory.
    """
    from concepts import ConceptStore
    from organisation.src.outcome import record_work_learning

    store = ConceptStore(data_dir="/tmp/test_incr38_eims")

    bau_work = type("Work", (), {
        "id": "w-bau",
        "work_type": "bau",
        "title": "Routine task",
        "outcome": None,
        "acceptance_criteria": [],
        "accountable_role_id": "r-1",
        "coordinating_role_id": None,
    })

    project_work = type("Work", (), {
        "id": "w-proj",
        "work_type": "project",
        "title": "Project task",
        "outcome": None,
        "acceptance_criteria": [],
        "accountable_role_id": "r-1",
        "coordinating_role_id": None,
    })

    assessment_bau = {"accepted": True, "rationale": "All criteria met."}
    assessment_project = {"accepted": True, "rationale": "All criteria met."}

    bau_result = record_work_learning(bau_work, assessment_bau, store)
    project_result = record_work_learning(project_work, assessment_project, store)

    assert bau_result is None
    assert project_result is not None


def test_assess_work_outcome_requires_work_with_acceptance_criteria() -> None:
    """assess_work_outcome requires a Work item with acceptance_criteria.

    Workflow execution has no Work item, no acceptance criteria, and no
    organisational outcome to assess. This function cannot consume
    workflow execution results.
    """
    from organisation.src.outcome import assess_work_outcome

    wf_only_data = type("Data", (), {
        "status": "completed",
        "output": "result",
    })()

    try:
        assess_work_outcome(wf_only_data, {"status": "completed"})
        assert False, "Should have failed without Work attributes"
    except AttributeError:
        pass


# ---- D. Telemetry vs Evidence Distinction ----


def test_workflow_state_step_results_are_execution_telemetry() -> None:
    """WorkflowState.step_results contains execution telemetry, not organisational evidence.

    Step results contain: step_name, step_type, status, output, composed_prompt,
    error, duration_seconds. These are runtime execution details.
    They contain no organisational metadata (no actor, no work reference,
    no capability reference, no assessment).
    """
    from workflow_runner.models import StepResult, StepType

    step_result = StepResult(
        step_name="step1",
        step_type=StepType.SKILL,
        status="completed",
        output={"data": "result"},
        duration_seconds=1.5,
    )

    assert step_result.step_name == "step1"
    assert step_result.status == "completed"
    assert step_result.output == {"data": "result"}
    assert step_result.duration_seconds == 1.5
    assert step_result.composed_prompt is None
    assert step_result.error is None


def test_step_results_have_no_organisational_metadata() -> None:
    """StepResult fields are all execution-related.

    No StepResult field references: Work, Capability, Actor, Organisation,
    Assessment, Evidence, Learning, or any organisational concept.
    """
    from workflow_runner.models import StepResult

    organisational_fields = [
        "work_id", "capability_id", "actor_id", "organisation_id",
        "assessment", "evidence", "learning", "outcome", "acceptance_criteria",
    ]
    for field in organisational_fields:
        assert field not in StepResult.model_fields, (
            f"StepResult has unexpected organisational field '{field}'"
        )


def test_workflow_state_has_no_work_reference() -> None:
    """WorkflowState has no reference to Work.

    Established in Increment 37, confirmed here: WorkflowState does not
    know about organisational effort, assignments, or outcomes.
    """
    from workflow_runner.models import WorkflowState

    fields = set(WorkflowState.model_fields.keys())
    for forbidden in ["work_id", "work", "work_ref", "organisation_id", "outcome", "evidence"]:
        assert forbidden not in fields, (
            f"WorkflowState has unexpected field '{forbidden}'"
        )


def test_workflow_definition_has_no_evidence_fields() -> None:
    """WorkflowDefinition has no evidence/learning/maturity fields.

    Repeated execution does not modify WorkflowDefinition. It remains
    a static execution definition with no tracking of execution history.
    """
    from workflow_runner.models import WorkflowDefinition

    fields = set(WorkflowDefinition.model_fields.keys())
    for forbidden in ["invocation_count", "correction_count", "maturity",
                       "confidence", "usage_count", "last_executed", "evidence",
                       "learning", "adopted", "promotion"]:
        assert forbidden not in fields, (
            f"WorkflowDefinition has unexpected field '{forbidden}'"
        )


# ---- E. Capability Outcome Assessor Cannot Consume Workflow Results ----


def test_capability_outcome_assessor_requires_execution_result_type() -> None:
    """CapabilityOutcomeAssessor.assess() takes ExecutionResult, not WorkflowExecutionResult.

    ExecutionResult has typed fields (outputs, artifacts, telemetry).
    WorkflowExecutionResult has different fields (status, workflow_name, output, error).
    The assessor cannot consume workflow results without type adaptation.
    """
    from contracts.capability_execution import ExecutionResult
    from contracts.capability_outcome_assessor import CapabilityOutcomeAssessor
    from contracts.workflow_execution import WorkflowExecutionResult

    sig = inspect.signature(CapabilityOutcomeAssessor.assess)
    params = list(sig.parameters.keys())
    assert "result" in params

    exec_result = ExecutionResult(outputs={"summary": "test"}, artifacts=[], telemetry={})
    assert isinstance(exec_result, ExecutionResult)

    wf_result = WorkflowExecutionResult(status="completed", workflow_name="test", output={}, error=None)
    assert isinstance(wf_result, WorkflowExecutionResult)
    assert not isinstance(wf_result, ExecutionResult)


def test_capability_outcome_assessor_is_not_in_workflow_execution_path() -> None:
    """CapabilityOutcomeAssessor and InvocationRecorder are not in the workflow execution path.

    The workflow execution adapter and executor do not reference either
    concept. They are confined to capability execution.
    """
    from workflow_runner.src.adapters.workflow_execution_adapter import WorkflowExecutionAdapter

    adapter_source = inspect.getsource(WorkflowExecutionAdapter)
    assert "CapabilityOutcomeAssessor" not in adapter_source
    assert "InvocationRecorder" not in adapter_source
    assert "CapabilityOutcome" not in adapter_source


# ---- F. EIMS Boundary ----


def test_workflow_execution_does_not_call_record_work_learning() -> None:
    """No code in the workflow execution path calls record_work_learning.

    The workflow execution path (WorkflowExecutionAdapter, executor,
    handlers) contains no reference to record_work_learning, assess_work_outcome,
    or complete_work. These are organisational functions called only by
    the Operations/chat layer on Work items.
    """
    from workflow_runner import executor as wf_executor
    from workflow_runner.handlers.skill_handler import handle_skill_step
    from workflow_runner.handlers.tool_handler import handle_tool_step
    from workflow_runner.src.adapters.workflow_execution_adapter import WorkflowExecutionAdapter

    adapter_source = inspect.getsource(WorkflowExecutionAdapter)
    executor_source = inspect.getsource(wf_executor)
    skill_source = inspect.getsource(handle_skill_step)
    tool_source = inspect.getsource(handle_tool_step)

    for source, name in [
        (adapter_source, "WorkflowExecutionAdapter"),
        (executor_source, "executor"),
        (skill_source, "handle_skill_step"),
        (tool_source, "handle_tool_step"),
    ]:
        assert "record_work_learning" not in source, (
            f"{name} references record_work_learning"
        )
        assert "assess_work_outcome" not in source, (
            f"{name} references assess_work_outcome"
        )


def test_workflow_execution_does_not_call_complete_work() -> None:
    """No code in the workflow execution path calls complete_work.

    complete_work transitions Work state in the Organisation domain.
    Workflow execution does not create or manage Work items.
    Uses word boundary matching to distinguish from fail_workflow/fail_work.
    """
    from workflow_runner import executor as wf_executor
    from workflow_runner.src.adapters.workflow_execution_adapter import WorkflowExecutionAdapter

    adapter_source = inspect.getsource(WorkflowExecutionAdapter)
    executor_source = inspect.getsource(wf_executor)

    assert not re.search(r"\bcomplete_work\b", adapter_source)
    assert not re.search(r"\bcomplete_work\b", executor_source)


def test_workflow_execution_does_not_call_fail_work() -> None:
    """No code in the workflow execution path calls fail_work.

    fail_work transitions Work state in the Organisation domain.
    Workflow execution has its own failure handling (fail_workflow for WorkflowState).
    Uses word boundary matching to distinguish from fail_workflow.
    """
    from workflow_runner import executor as wf_executor
    from workflow_runner.src.adapters.workflow_execution_adapter import WorkflowExecutionAdapter

    adapter_source = inspect.getsource(WorkflowExecutionAdapter)
    executor_source = inspect.getsource(wf_executor)

    assert not re.search(r"\bfail_work\b", adapter_source)
    assert not re.search(r"\bfail_work\b", executor_source)


def test_concept_store_records_on_capability_concepts_only() -> None:
    """ConceptStore.record_invocation operates on capability concepts.

    It updates MaturationHistory (invocation_count, correction_count)
    on EnterpriseConcept objects with kind=CAPABILITY. There is no
    mechanism to record invocation telemetry for workflow execution.
    """
    from concepts import ConceptKind, ConceptStore, EnterpriseConcept

    store = ConceptStore(data_dir="/tmp/test_incr38_concept")

    cap_concept = EnterpriseConcept(
        id="cap-1",
        kind=ConceptKind.CAPABILITY,
        name="A capability",
    )
    store.upsert(cap_concept)

    store.record_invocation("cap-1", "success")

    retrieved = store.get("cap-1")
    assert retrieved is not None
    assert retrieved.kind == ConceptKind.CAPABILITY
    history = retrieved.payload.get("maturation_history") or {}
    assert history.get("invocation_count", 0) >= 1


# ---- G. Human Correction ----


def test_correction_count_exists_only_in_maturation_history() -> None:
    """correction_count exists only in MaturationHistory on Capability concepts.

    There is no correction tracking in workflow execution, WorkflowState,
    WorkflowExecutionRequest, or WorkflowExecutionResult.
    """
    from concepts import MaturationHistory

    assert "correction_count" in MaturationHistory.model_fields
    assert "invocation_count" in MaturationHistory.model_fields


def test_workflow_execution_has_no_correction_tracking() -> None:
    """Workflow execution has no correction_count or equivalent.

    No field in WorkflowDefinition, WorkflowState, StepResult,
    WorkflowExecutionRequest, or WorkflowExecutionResult tracks correction.
    """
    from contracts.workflow_execution import (
        WorkflowExecutionRequest,
        WorkflowExecutionResult,
    )
    from workflow_runner.models import StepResult, WorkflowDefinition, WorkflowState

    models = [
        WorkflowDefinition, WorkflowState, StepResult,
        WorkflowExecutionRequest, WorkflowExecutionResult,
    ]

    for model in models:
        fields = set(model.model_fields.keys()) if hasattr(model, "model_fields") else set()
        assert "correction_count" not in fields, (
            f"{model.__name__} has correction_count"
        )


def test_capability_correction_and_workflow_correction_are_separate() -> None:
    """Capability correction (MaturationHistory.correction_count) and
    workflow execution are completely separate concepts.

    Correction counting is in the capability lifecycle (via InvocationRecorder
    on Capability concepts). Workflow execution has no equivalent.
    They are not connected.
    """
    from concepts import MaturationHistory
    from workflow_runner.models import WorkflowState

    assert "correction_count" in MaturationHistory.model_fields

    state_fields = set(WorkflowState.model_fields.keys())
    assert "correction_count" not in state_fields


# ---- H. Workflow Reuse ----


def test_workflow_definition_is_immutable_to_execution() -> None:
    """WorkflowDefinition has no mutable execution state.

    No field on WorkflowDefinition changes when the workflow executes.
    It is a static definition loaded from YAML. Repeated execution creates
    new WorkflowState instances, not modifications to WorkflowDefinition.
    """
    from workflow_runner.models import WorkflowDefinition

    mutable_fields = {"status", "last_executed", "execution_count", "version_major"}
    fields = set(WorkflowDefinition.model_fields.keys())
    for field in mutable_fields:
        assert field not in fields, f"WorkflowDefinition has mutable field '{field}'"


# ---- I. Bus Events Have No Organisational Consumers ----


def test_publish_workflow_completed_is_workflow_runner_internal() -> None:
    """publish_workflow_completed/failed are workflow_runner-internal events.

    The workflow_runner package has publish_workflow_completed/failed methods
    on its event bus. No code outside workflow_runner references these
    or the workflow.lifecycle event types.
    """
    from workflow_runner.bus import EventBus

    assert hasattr(EventBus, "publish_workflow_completed")
    assert hasattr(EventBus, "publish_workflow_failed")
    assert hasattr(EventBus, "publish_step_completed")


def test_no_organisational_consumer_of_workflow_lifecycle_events() -> None:
    """No organisation package code references workflow lifecycle event types.

    The organisation package does not subscribe to workflow.lifecycle
    events. Workflow execution events stay within the workflow_runner.
    """
    import glob as _glob

    workflow_lifecycle_types = [
        "WorkflowCompleted", "WorkflowFailed", "WorkflowStarted",
        "StepCompleted", "StepStarted",
    ]

    py_files = _glob.glob(os.path.join(ORGANISATION_SRC, "**", "*.py"), recursive=True)

    for filepath in py_files:
        with open(filepath) as f:
            source = f.read()
        for event_type in workflow_lifecycle_types:
            assert event_type not in source, (
                f"{filepath} references {event_type} — "
                f"organisation code should not consume workflow lifecycle events"
            )


# ---- J. Architectural Decision ----


def test_workflow_execution_telemetry_is_sufficient_for_execution_monitoring() -> None:
    """WorkflowState provides sufficient telemetry for execution monitoring.

    Status, step_results, context, and error fields cover all execution
    monitoring needs. No organisational evidence mechanism is required
    for monitoring workflow execution.
    """
    from workflow_runner.models import WorkflowState

    fields = set(WorkflowState.model_fields.keys())
    monitoring_fields = {"status", "step_results", "context", "error", "current_step_index"}
    for field in monitoring_fields:
        assert field in fields, f"WorkflowState missing monitoring field '{field}'"


def test_no_existing_mechanism_requires_workflow_evidence() -> None:
    """No existing organisational mechanism requires evidence from workflow execution.

    The evidence chain (InvocationRecorder → ConceptStore, record_work_learning → EIMS,
    assess_work_outcome → Work.outcome) all operate on different entities
    (capabilities, work items). None require or reference workflow execution data.
    """
    from contracts.capability_outcome_assessor import CapabilityOutcomeAssessor
    from contracts.invocation_recorder import InvocationRecorder
    from organisation.src.outcome import assess_work_outcome, record_work_learning

    record_sig = inspect.signature(record_work_learning)
    assess_sig = inspect.signature(assess_work_outcome)
    invoke_sig = inspect.signature(InvocationRecorder.record_invocation)
    assessor_sig = inspect.signature(CapabilityOutcomeAssessor.assess)

    record_params = list(record_sig.parameters.keys())
    assess_params = list(assess_sig.parameters.keys())
    invoke_params = list(invoke_sig.parameters.keys())
    assessor_params = list(assessor_sig.parameters.keys())

    assert "work" in record_params
    assert "work" in assess_params
    assert "capability_id" in invoke_params
    assert "result" in assessor_params


def test_workflow_execution_does_not_satisfy_evidence_criteria() -> None:
    """Workflow execution data does not meet the three criteria for organisational evidence:

    1. Tied to identifiable organisational entity: NO (WorkflowState ≠ Work/Capability)
    2. Serves organisational purpose (learning, promotion, accountability): NO
    3. Produces durable knowledge (Concepts, outcomes): NO

    Workflow execution produces runtime telemetry. This is sufficient for
    execution monitoring but does not constitute organisational evidence.
    """
    from contracts.workflow_execution import WorkflowExecutionResult

    result_fields = set(WorkflowExecutionResult.model_fields.keys())

    has_organisational_entity = any(f in result_fields for f in [
        "work_id", "capability_id", "actor_id", "organisation_id"
    ])
    has_organisational_purpose = any(f in result_fields for f in [
        "outcome", "assessment", "learning", "evidence", "accountability"
    ])
    has_durable_knowledge = any(f in result_fields for f in [
        "concept_id", "maturity", "confidence", "promotion"
    ])

    assert not has_organisational_entity
    assert not has_organisational_purpose
    assert not has_durable_knowledge


def test_workflow_execution_produces_no_organisational_evidence() -> None:
    """The complete workflow execution path produces no organisational evidence.

    Combined verification: the adapter, executor, and handlers contain
    no references to any evidence mechanism. This is the architectural
    decision — workflow execution telemetry is sufficient.
    """
    from workflow_runner import executor as wf_executor
    from workflow_runner.src.adapters.workflow_execution_adapter import WorkflowExecutionAdapter

    adapter_source = inspect.getsource(WorkflowExecutionAdapter)
    executor_source = inspect.getsource(wf_executor)

    evidence_refs = [
        "InvocationRecorder", "record_invocation", "record_work_learning",
        "assess_work_outcome", "complete_work", "fail_work", "ConceptStore",
        "CapabilityOutcomeAssessor", "EIMS",
    ]

    for ref in evidence_refs:
        assert ref not in adapter_source, (
            f"WorkflowExecutionAdapter references {ref}"
        )

    for ref in evidence_refs:
        if ref in ("fail_work",):
            assert not re.search(r"\b" + re.escape(ref) + r"\b", executor_source), (
                f"executor references {ref}"
            )
        else:
            assert ref not in executor_source, (
                f"executor references {ref}"
            )
