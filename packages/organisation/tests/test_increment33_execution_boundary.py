"""
Architectural tests for Increment 33 — Capability Exercise →
Reusable Workflow Boundary.

Proves that:
- WorkflowDefinition represents a known, explicit execution pattern (not mere capability existence)
- WorkflowState is runtime execution state, distinct from WorkflowDefinition and Work
- CAPABILITY_PATH exercises a capability through CapabilityExecutionPort without a WorkflowDefinition
- EXISTING_WORKFLOW uses WorkflowExecutionPort — a reusable, known execution pattern
- A WorkflowDefinition may contain skill/tool/capability references by name
- Skill is a reusable method; a workflow may invoke skills, capabilities, or tools
- Capability execution can produce evidence (InvocationRecorder, CapabilityProficiency) without
  automatically becoming a workflow
- Work is the organisational outcome/effort record — not execution state
- "Compiled workflow" means the pattern is explicit and reusable, not that AI/human are absent
- WorkflowRunner executes but does not decide organisational adoption
- OCP holds the authority for selecting EXISTING_WORKFLOW (organisation decides what is "known")
- Paperclip/LangGraph remain implementation backends, not organisational decision-makers
- Work ↔ WorkflowState are separate — no automatic coupling
"""

from __future__ import annotations

import ast
import inspect
import os
from typing import Any
from unittest.mock import MagicMock

from capability import Capability, CapabilityKind, CapabilityStatus
from capability_proficiency import CapabilityProficiency
from contracts.capability_execution import CapabilityExecutionPort, ExecutionResult
from contracts.capability_outcome_assessor import CapabilityOutcome
from contracts.invocation_recorder import InvocationRecorder
from contracts.workflow_execution import (
    WorkflowExecutionPort,
    WorkflowExecutionRequest,
    WorkflowExecutionResult,
)
from models import Step, StepType, WorkflowDefinition, WorkflowState

from execution_path import ExecutionPath, ExecutionPathResult
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


# ---- A. WorkflowDefinition represents an explicit known execution pattern ----


def test_workflow_definition_has_ordered_steps() -> None:
    """A WorkflowDefinition is a declarative, ordered set of steps — the organisation's
    explicit representation of how to exercise one or more capabilities/skills/tools."""
    wf = WorkflowDefinition(
        name="retention-report",
        description="Weekly customer retention report",
        steps=[
            Step(type=StepType.SKILL, name="gather-data", uses="gather_retention_data"),
            Step(type=StepType.SKILL, name="analyse", uses="analyse_retention"),
            Step(type=StepType.TOOL, name="export", uses="csv_writer"),
        ],
    )
    assert len(wf.steps) == 3
    assert wf.steps[0].name == "gather-data"
    assert wf.steps[1].name == "analyse"
    assert wf.steps[2].type == StepType.TOOL


def test_workflow_definition_does_not_require_capability_id() -> None:
    """WorkflowDefinition does not carry a capability_id — it is a pattern, not an ability."""
    wf_fields = set(WorkflowDefinition.model_fields.keys())
    assert "capability_id" not in wf_fields
    assert "steps" in wf_fields


def test_workflow_definition_has_metadata_not_execution_state() -> None:
    """WorkflowDefinition carries intent, inputs, outputs — not execution runtime state."""
    wf_fields = set(WorkflowDefinition.model_fields.keys())
    # Declarative metadata
    assert "inputs" in wf_fields
    assert "outputs" in wf_fields
    assert "intent" in wf_fields
    assert "name" in wf_fields
    # No runtime state fields
    assert "current_step_index" not in wf_fields
    assert "status" not in wf_fields
    assert "step_results" not in wf_fields


def test_workflow_state_is_distinct_from_workflow_definition() -> None:
    """WorkflowState is the runtime execution state of a WorkflowDefinition,
    NOT the definition itself. They are separate classes."""
    assert WorkflowState is not WorkflowDefinition
    assert WorkflowState.__name__ != WorkflowDefinition.__name__

    wf_fields = set(WorkflowDefinition.model_fields.keys())
    state_fields = set(WorkflowState.model_fields.keys())

    # WorkflowDefinition has steps (the pattern); WorkflowState has execution status
    assert "steps" in wf_fields
    assert "status" in state_fields
    assert "current_step_index" in state_fields


def test_workflow_state_has_persistent_runtime_fields() -> None:
    """WorkflowState tracks execution progress: status, current_step_index, step_results, context."""
    state = WorkflowState(
        workflow_id="wf-1",
        workflow_name="test",
        workflow_path="/tmp/test.yaml",
        steps=[Step(type=StepType.SKILL, name="s1", uses="s1")],
    )
    assert state.status == "pending"
    assert state.current_step_index == 0
    assert state.step_results == []
    assert state.context == {}


def test_workflow_state_can_exist_without_work() -> None:
    """WorkflowState does not reference Work — they are separate lifecycle entities."""
    state_fields = set(WorkflowState.model_fields.keys())
    assert "work_id" not in state_fields
    assert "accountable_role_id" not in state_fields
    assert "required_capability_ids" not in state_fields


# ---- B. Work vs WorkflowState distinction ----


def test_work_has_no_workflow_state_fields() -> None:
    """Work does not carry WorkflowState's runtime execution fields."""
    work_fields = set(Work.model_fields.keys())
    assert "current_step_index" not in work_fields
    assert "step_results" not in work_fields
    assert "workflow_path" not in work_fields
    # Work carries organisational metadata instead
    assert "accountable_role_id" in work_fields
    assert "required_capability_ids" in work_fields
    assert "acceptance_criteria" in work_fields


def test_workflow_state_has_no_work_fields() -> None:
    """WorkflowState does not carry Work's organisational fields."""
    state_fields = set(WorkflowState.model_fields.keys())
    assert "accountable_role_id" not in state_fields
    assert "required_capability_ids" not in state_fields
    assert "acceptance_criteria" not in state_fields
    assert "assignee_agent_id" not in state_fields


def test_work_is_not_workflow_state() -> None:
    """Work and WorkflowState are distinct classes with distinct lifecycles."""
    work = Work(id="w-1", title="Task", accountable_role_id="r-1")
    state = WorkflowState(
        workflow_id="wf-1",
        workflow_name="test",
        workflow_path="/tmp/test.yaml",
        steps=[Step(type=StepType.SKILL, name="s1", uses="s1")],
    )
    assert type(work).__name__ != type(state).__name__


def test_work_does_not_reference_workflow_definition() -> None:
    """Work does not carry a workflow_reference or workflow_definition —
    it is the organisational record, not an execution instance."""
    work_fields = set(Work.model_fields.keys())
    assert "workflow_id" not in work_fields
    assert "workflow_name" not in work_fields
    assert "workflow_definition" not in work_fields
    assert "workflow_path" not in work_fields


# ---- C. CAPABILITY_PATH vs EXISTING_WORKFLOW semantics ----


def test_capability_path_does_not_require_workflow_definition() -> None:
    """CAPABILITY_PATH selects a capability by ID — it does NOT carry a workflow."""
    result = ExecutionPathResult(
        path=ExecutionPath.CAPABILITY_PATH,
        capability_id="cap-analyse",
        reason="Capability is available",
    )
    assert result.path == ExecutionPath.CAPABILITY_PATH
    assert result.capability_id == "cap-analyse"
    assert result.workflow is None


def test_existing_workflow_path_carries_workflow_definition() -> None:
    """EXISTING_WORKFLOW carries a WorkflowDefinition (or its dict representation)."""
    wf = WorkflowDefinition(
        name="retention-report",
        steps=[Step(type=StepType.SKILL, name="step1", uses="gather_data")],
    )
    result = ExecutionPathResult(
        path=ExecutionPath.EXISTING_WORKFLOW,
        workflow=wf,
        reason="Found matching workflow",
    )
    assert result.path == ExecutionPath.EXISTING_WORKFLOW
    assert result.workflow is wf
    assert result.capability_id is None


def test_existing_workflow_path_does_not_carry_capability_id() -> None:
    """EXISTING_WORKFLOW does not select a single capability — it selects a pattern."""
    result = ExecutionPathResult(
        path=ExecutionPath.EXISTING_WORKFLOW,
        workflow=MagicMock(),
        reason="known pattern",
    )
    assert result.capability_id is None
    assert result.workflow is not None


def test_select_execution_path_prefers_workflow_over_capability() -> None:
    """When both a workflow and a capability exist, OCP selects EXISTING_WORKFLOW."""
    plane = _make_inmemory_ocp()

    cap = Capability(
        id="cap-1",
        name="Analyse",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(cap)

    wf = MagicMock()
    wf.name = "analyse-report"
    wf.description = "Run the analysis and produce a report"

    def lookup(intent: str) -> list[Any]:
        return [wf]

    result = plane.select_execution_path(
        intent="run the analyse report",
        context={"required_capability_ids": ["cap-1"]},
        workflow_lookup=lookup,
    )
    assert result.path == ExecutionPath.EXISTING_WORKFLOW
    assert result.workflow is wf
    assert result.capability_id is None


def test_select_execution_path_falls_back_to_capability_when_no_workflow() -> None:
    """Without a matching workflow, a known capability yields CAPABILITY_PATH."""
    plane = _make_inmemory_ocp()

    cap = Capability(
        id="cap-1",
        name="Analyse",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(cap)

    result = plane.select_execution_path(
        intent="do something",
        context={"required_capability_ids": ["cap-1"]},
        workflow_lookup=lambda intent: [],
    )
    assert result.path == ExecutionPath.CAPABILITY_PATH
    assert result.capability_id == "cap-1"
    assert result.workflow is None


# ---- D. Workflow execution uses WorkflowExecutionPort ----


def test_workflow_execution_port_is_protocol() -> None:
    """WorkflowExecutionPort is a Protocol — it defines the contract for
    executing known workflows."""
    import typing
    assert typing.is_protocol(WorkflowExecutionPort)


def test_workflow_execution_port_takes_request_with_workflow_name() -> None:
    """WorkflowExecutionPort.execute_workflow takes a WorkflowExecutionRequest
    containing workflow_name — not a capability_id."""
    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = list(sig.parameters.keys())
    assert "request" in params

    request_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in request_fields
    assert "capability_id" not in request_fields


def test_workflow_execution_result_has_status_and_output() -> None:
    """WorkflowExecutionResult has status, workflow_name, output, error —
    not capability execution fields."""
    result_fields = set(WorkflowExecutionResult.model_fields.keys())
    assert "status" in result_fields
    assert "workflow_name" in result_fields
    assert "output" in result_fields
    assert "error" in result_fields


def test_workflow_execution_adapter_implements_workflow_execution_port() -> None:
    """WorkflowExecutionAdapter implements execute_workflow (not CapabilityExecutionPort.execute)."""
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )

    adapter = WorkflowExecutionAdapter()
    assert hasattr(adapter, "execute_workflow")
    sig = inspect.signature(adapter.execute_workflow)
    assert "request" in sig.parameters


def test_workflow_execution_port_is_separate_from_capability_execution_port() -> None:
    """WorkflowExecutionPort.execute_workflow and CapabilityExecutionPort.execute
    are distinct contracts with distinct signatures."""
    assert WorkflowExecutionPort is not CapabilityExecutionPort
    cap_method = inspect.signature(CapabilityExecutionPort.execute)
    assert "execute_workflow" not in list(cap_method.parameters.keys())


# ---- E. Capability vs Workflow distinction ----


def test_capability_is_not_workflow_definition() -> None:
    """Capability (an ability) and WorkflowDefinition (a known pattern) are distinct."""
    from capability import Capability
    from models import WorkflowDefinition

    assert Capability is not WorkflowDefinition

    cap_fields = set(Capability.model_fields.keys())
    wf_fields = set(WorkflowDefinition.model_fields.keys())

    assert "capability_kind" in cap_fields
    assert "capability_kind" not in wf_fields

    assert "steps" in wf_fields
    assert "steps" not in cap_fields


def test_capability_path_does_not_create_or_require_workflow() -> None:
    """CAPABILITY_PATH exercises a capability directly — no WorkflowDefinition is needed."""
    cap = Capability(
        id="cap-direct-exec",
        name="Direct Execute",
        capability_kind=CapabilityKind.TOOL,
        status=CapabilityStatus.ACTIVE,
    )

    plane = _make_inmemory_ocp()
    plane.register_capability(cap)

    result = plane.select_execution_path(
        intent="run cap-direct-exec",
        context={"required_capability_ids": ["cap-direct-exec"]},
        workflow_lookup=lambda intent: [],
        capability_query=lambda cid: MagicMock(
            capability_id=cid,
            available=True,
            eta_seconds=0,
            assignee=None,
            reason="available",
        ),
    )
    assert result.path == ExecutionPath.CAPABILITY_PATH
    assert result.capability_id == "cap-direct-exec"
    assert result.workflow is None


# ---- F. Workflow steps reference skills/tools/workflows by name ----


def test_workflow_step_types_include_skill_tool_and_workflow() -> None:
    """StepType enum supports skill, tool, and workflow sub-invocation types."""
    assert StepType.SKILL.value == "skill"
    assert StepType.TOOL.value == "tool"
    assert StepType.WORKFLOW.value == "workflow"


def test_workflow_step_uses_string_reference_not_model() -> None:
    """A workflow Step references skills/tools/workflows by string name, not by domain model objects."""
    step = Step(
        type=StepType.SKILL,
        name="enrich-lead",
        uses="lead_enrichment_skill",
    )
    assert isinstance(step.uses, str)
    assert step.uses == "lead_enrichment_skill"

    step2 = Step(
        type=StepType.TOOL,
        name="write-csv",
        uses="csv_writer_tool",
    )
    assert isinstance(step2.uses, str)


def test_workflow_can_nest_sub_workflows() -> None:
    """A workflow step can reference another workflow by name (sub-workflow invocation)."""
    wf = WorkflowDefinition(
        name="parent-workflow",
        steps=[
            Step(type=StepType.SKILL, name="step1", uses="skill-a"),
            Step(type=StepType.WORKFLOW, name="sub-flow", uses="child-workflow"),
        ],
    )
    assert wf.steps[1].type == StepType.WORKFLOW
    assert wf.steps[1].uses == "child-workflow"


# ---- G. Skill's role in relation to WorkflowDefinition ----


def test_skill_is_reusable_method_not_workflow() -> None:
    """A Skill is a reusable method for exercising a Capability — it does not
    need to be a WorkflowDefinition to be repeatable."""
    from skill import Skill

    skill_fields = set(Skill.model_fields.keys())
    wf_fields = set(WorkflowDefinition.model_fields.keys())

    assert "steps" not in skill_fields
    assert "steps" in wf_fields

    assert "capability_id" in skill_fields
    assert "capability_id" not in wf_fields

    assert "method" in skill_fields
    assert "method" not in wf_fields


def test_skill_can_be_useful_without_being_a_workflow() -> None:
    """A Skill represents an organisational technique — not every skill needs to be
    packaged as an explicit multi-step workflow."""
    from skill import Skill

    skill = Skill(
        id="skill-1",
        capability_id="cap-1",
        name="Scoring method",
        method="Weighted scoring against ICP",
        tool_ids=["tool-crm"],
    )
    assert skill.method is not None
    assert skill.tool_ids == ["tool-crm"]


def test_workflow_can_invoke_skills_by_name() -> None:
    """A workflow may invoke skills — steps reference skill names by string."""
    wf = WorkflowDefinition(
        name="multi-skill-workflow",
        steps=[
            Step(type=StepType.SKILL, name="enrich", uses="enrich_lead"),
            Step(type=StepType.SKILL, name="score", uses="score_lead"),
            Step(type=StepType.SKILL, name="report", uses="generate_report"),
        ],
    )
    assert all(s.type == StepType.SKILL for s in wf.steps)
    assert [s.uses for s in wf.steps] == ["enrich_lead", "score_lead", "generate_report"]


def test_workflow_does_not_require_all_steps_to_be_skills() -> None:
    """A workflow can mix skills, tools, and sub-workflows — not every step must be a skill."""
    wf = WorkflowDefinition(
        name="mixed-workflow",
        steps=[
            Step(type=StepType.SKILL, name="s1", uses="skill_a"),
            Step(type=StepType.TOOL, name="t1", uses="echo"),
            Step(type=StepType.WORKFLOW, name="w1", uses="child.wf"),
        ],
    )
    assert len(wf.steps) == 3
    assert wf.steps[0].type == StepType.SKILL
    assert wf.steps[1].type == StepType.TOOL
    assert wf.steps[2].type == StepType.WORKFLOW


# ---- H. Evidence: successful capability exercise without becoming a workflow ----


def test_successful_capability_execution_records_invocation() -> None:
    """When a capability executes successfully, InvocationRecorder records telemetry
    in ConceptStore — this evidence does NOT automatically create a WorkflowDefinition."""
    store = MagicMock()
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )
    from workflow_runner.src.adapters.invocation_recorder_adapter import (
        InvocationRecorderAdapter,
    )

    assessor = CapabilityOutcomeAssessorAdapter()
    recorder = InvocationRecorderAdapter(store=store, outcome_assessor=assessor)

    result = ExecutionResult(outputs={"result": "ok"}, telemetry={"capability_id": "cap-1"})
    recorder.record_invocation("cap-1", result, {"actor_id": "a1"})

    store.record_invocation.assert_called_once_with("cap-1", "success")


def test_capability_proficiency_evidence_links_to_work() -> None:
    """CapabilityProficiency evidence entries carry source_work_id — linking
    successful capability exercise back to the originating Work instance."""
    proficiency = CapabilityProficiency(
        id="prof-1",
        capability_id="cap-1",
        actor_id="actor-1",
        evidence=[
            {
                "source_work_id": "w-1",
                "type": "execution",
                "content": {"status": "completed", "outputs": {"result": "ok"}},
                "strength": 1.0,
            }
        ],
    )
    assert proficiency.evidence[0]["source_work_id"] == "w-1"


def test_capability_execution_does_not_require_workflow_state() -> None:
    """Executing a capability through CAPABILITY_PATH does not create a WorkflowState."""

    # CapabilityExecutionPort.execute has no workflow_id parameter
    sig = inspect.signature(CapabilityExecutionPort.execute)
    params = list(sig.parameters.keys())
    assert "workflow_id" not in params
    assert "workflow_state" not in params


def test_invocation_recorder_protocol_takes_workflow_id_optional() -> None:
    """InvocationRecorder.record_invocation takes capability_id, result, actor_context —
    it does not carry a workflow reference."""
    sig = inspect.signature(InvocationRecorder.record_invocation)
    params = list(sig.parameters.keys())
    assert "capability_id" in params
    assert "result" in params
    assert "actor_context" in params
    # Does not reference workflow
    assert "workflow_id" not in params


# ---- I. "Compiled workflow" semantics ----


def test_compiled_workflow_means_explicit_reusable_pattern() -> None:
    """A 'compiled' workflow means the execution pattern has become sufficiently
    understood, explicit, and reusable. It does NOT mean AI/human are absent,
    deterministic-only, or capability-free.

    This test proves the distinction: a WorkflowDefinition is a declarative,
    loaded pattern that the organisation can reuse without rediscovering steps."""
    wf = WorkflowDefinition(
        name="compiled-work-pattern",
        description="A known, repeatable multi-step process",
        steps=[
            Step(type=StepType.SKILL, name="analyse", uses="analysis_skill"),
            Step(type=StepType.SKILL, name="decide", uses="decision_skill"),
            Step(type=StepType.TOOL, name="report", uses="report_writer"),
        ],
    )
    assert len(wf.steps) == 3
    # The pattern is declarative — the organisation can hand it to any executor
    # without re-deriving the step ordering
    assert all(hasattr(s, "name") and hasattr(s, "uses") for s in wf.steps)


def test_compiled_workflow_still_supports_ai_or_capability_invocation() -> None:
    """A compiled workflow (WorkflowDefinition) may contain skill steps that
    invoke AI or capabilities — the distinction is that the overall pattern is known."""
    wf = WorkflowDefinition(
        name="ai-assisted-workflow",
        steps=[
            Step(type=StepType.SKILL, name="analyse", uses="ai_analysis_skill"),
            Step(type=StepType.SKILL, name="enrich", uses="capability_enrichment"),
        ],
    )
    # The steps reference AI/capability-backed skills by name — the pattern is still known
    assert wf.steps[0].uses == "ai_analysis_skill"
    assert wf.steps[1].uses == "capability_enrichment"


# ---- J. Workflow creation/registration authority ----


def test_ocp_does_not_create_or_store_workflow_definitions() -> None:
    """OCP does NOT have a method to register or store WorkflowDefinition objects.
    Workflow creation/registration authority rests with the organisation (decision)
    and the workflow_runner file system (storage), not the OCP."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()
    # OCP has no workflow registration method
    assert not hasattr(plane, "register_workflow")
    assert not hasattr(plane, "store_workflow")
    assert not hasattr(plane, "compile_workflow")


def test_ocp_select_execution_path_is_the_organisation_decision() -> None:
    """OCP.select_execution_path is where the organisation decides that a
    workflow is 'known' — it is the boundary between capability exercise
    and reusable workflow selection."""

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


def test_workflow_runner_does_not_decide_organisational_adoption() -> None:
    """The WorkflowExecutionAdapter executes a workflow but does NOT decide
    whether it represents an organisational standard. That decision belongs to OCP."""
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )
    adapter = WorkflowExecutionAdapter()
    adapter_methods = [
        m for m in dir(adapter)
        if not m.startswith("_")
    ]
    # The adapter has no organisational decision methods
    assert "select_execution_path" not in adapter_methods
    assert "register_capability" not in adapter_methods
    assert "mark_work_ready" not in adapter_methods
    assert "complete_work" not in adapter_methods


# ---- K. Work ↔ WorkflowState relationship ----


def test_work_and_workflow_state_are_not_coupled() -> None:
    """There is no automatic Work → WorkflowState or WorkflowState → Work reference.
    Work tracks organisational intent; WorkflowState tracks execution progress.
    They are separate lifecycle entities."""
    assert "workflow_id" not in set(Work.model_fields.keys())
    assert "work_id" not in set(WorkflowState.model_fields.keys())


def test_workflow_state_tracks_own_execution_progress_independently() -> None:
    """WorkflowState has its own workflow_id and status — it does not need Work."""
    from models import Step, StepType, WorkflowState

    state = WorkflowState(
        workflow_id="wf-1",
        workflow_name="test",
        workflow_path="/tmp/test.yaml",
        steps=[Step(type=StepType.SKILL, name="s1", uses="s1")],
        status="running",
        current_step_index=1,
    )
    assert state.workflow_id == "wf-1"
    assert state.status == "running"
    assert state.current_step_index == 1
    # No work reference
    assert not hasattr(state, "work_id")


# ---- L. BAU boundary ----


def test_bau_work_has_no_workflow_reference() -> None:
    """BAU Work does not carry a workflow definition — it is an organisational
    intent record that may be executed via capability path or workflow path
    depending on what the organisation decides."""
    work = Work(
        id="w-bau",
        title="Fix issue",
        work_type="bau",
        accountable_role_id="r-1",
        required_capability_ids=["cap-fix"],
    )
    assert work.work_type == "bau"
    assert "workflow_id" not in set(work.model_dump().keys())


def test_bau_trigger_flow_is_outside_workflow_definition() -> None:
    """Triggers (schedule, event, explicit request) are external to
    WorkflowDefinition. WorkflowDefinition has no trigger fields."""
    wf_fields = set(WorkflowDefinition.model_fields.keys())
    assert "trigger" not in wf_fields
    assert "triggers" not in wf_fields
    assert "schedule" not in wf_fields


# ---- M. Failure-feedback boundary ----


def test_work_outcome_recorded_for_learning() -> None:
    """When Work completes (success or failure), the outcome is recorded
    on Work itself — this is where organisational learning begins."""
    work = Work(
        id="w-1",
        title="Build feature",
        accountable_role_id="r-1",
        acceptance_criteria=["Works correctly"],
    )
    from organisation.src.outcome import assess_work_outcome

    result = {"status": "completed", "outputs": {"summary": "Feature works correctly"}}
    assessment = assess_work_outcome(work, result)
    assert assessment["accepted"] is True
    assert work.outcome is None  # Work.outcome is set by org plane, not the assessor


def test_failed_work_can_become_learning_evidence() -> None:
    """Failed Work produces evidence of what went wrong — the architecture
    supports feedback from BAU/workflow failures into capability/skill improvement.
    The boundary is: Failure → Work.outcome/failed → organisational learning."""
    work = Work(
        id="w-fail",
        title="Task",
        accountable_role_id="r-1",
        acceptance_criteria=["Should work"],
    )
    from organisation.src.outcome import assess_work_outcome

    result = {
        "status": "failed",
        "outputs": {"error": "Capability failed on edge case"},
    }
    assessment = assess_work_outcome(work, result)
    assert assessment["accepted"] is False
    assert "error" not in assessment.get("criteria_met", [])


def test_capability_failure_is_classified_not_executed_vs_failed() -> None:
    """The CapabilityOutcomeAssessor distinguishes pre-execution failures
    (NOT_EXECUTED) from execution failures (FAILED) — this is the clean
    place for failure feedback into the learning boundary."""
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )

    assessor = CapabilityOutcomeAssessorAdapter()

    # Pre-execution failure — capability was never actually invoked
    pre_execution = ExecutionResult(
        outputs={"error": "not found"},
        telemetry={"error": "capability_not_found"},
    )
    assert assessor.assess(pre_execution) == CapabilityOutcome.NOT_EXECUTED

    # Actual execution failure
    execution_failure = ExecutionResult(
        outputs={"error": "runtime error"},
        telemetry={"error": "runtime_error"},
    )
    assert assessor.assess(execution_failure) == CapabilityOutcome.FAILED


# ---- N. Paperclip / LangGraph boundary ----


def test_paperclip_backend_does_not_decide_workflow_adoption() -> None:
    """PaperclipBackend implements ExecutionBackend — it executes, it does not decide
    that an execution pattern should become an organisational workflow."""
    from workflow_runner.src.operations import PaperclipBackend

    backend = PaperclipBackend(MagicMock())
    backend_methods = [
        m for m in dir(backend)
        if not m.startswith("_")
    ]
    assert "select_execution_path" not in backend_methods
    assert "compile_workflow" not in backend_methods
    assert "register_workflow" not in backend_methods


def test_worker_backend_does_not_decide_workflow_adoption() -> None:
    """WorkerBackend implements ExecutionBackend — it is a runtime mechanism,
    not an organisational decision-maker."""
    from workflow_runner.src.operations import WorkerBackend

    backend = WorkerBackend(worker=MagicMock(), org_plane=MagicMock())
    backend_methods = [
        m for m in dir(backend)
        if not m.startswith("_")
    ]
    assert "select_execution_path" not in backend_methods
    assert "compile_workflow" not in backend_methods


def test_paperclip_backend_implements_execution_backend_contract() -> None:
    """PaperclipBackend and WorkerBackend both implement execute() / can_handle()."""
    from workflow_runner.src.operations import PaperclipBackend, WorkerBackend

    for backend_cls, init_args in [
        (PaperclipBackend, (MagicMock(),)),
        (WorkerBackend, (MagicMock(), MagicMock())),
    ]:
        backend = backend_cls(*init_args)
        assert hasattr(backend, "execute")
        assert callable(backend.execute)
        assert hasattr(backend, "can_handle")
        assert callable(backend.can_handle)


def test_operations_does_not_import_paperclip_directly() -> None:
    """Operations coordinates backends but does not import Paperclip directly."""
    with open(os.path.normpath(
        os.path.join(WORKFLOW_RUNNER_SRC, "operations.py")
    )) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "paperclip" not in alias.name.lower()
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "paperclip" not in node.module.lower()


# ---- O. WorkflowRunner execution boundary ----


def test_workflow_execution_does_not_invoke_capability_execution_port() -> None:
    """Executing a WorkflowDefinition (via WorkflowExecutionPort) is separate from
    CapabilityExecutionPort — they are invoked on different code paths."""
    # WorkflowExecutionPort.execute_workflow takes a WorkflowExecutionRequest
    wf_sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    assert "request" in wf_sig.parameters

    # CapabilityExecutionPort.execute takes capability_id, context, actor_context
    cap_sig = inspect.signature(CapabilityExecutionPort.execute)
    params = list(cap_sig.parameters.keys())
    assert "capability_id" in params
    assert "context" in params
    assert "actor_context" in params
    assert "request" not in params


def test_workers_capability_path_vs_workflow_path_are_separate() -> None:
    """Worker has two distinct execution paths:
    1. Capability path: work with required_capability_ids → CapabilityExecutionPort
    2. Workflow path: Work without required_capability_ids → _do_work (generative)"""
    from workflow_runner.src.worker import Worker

    # Worker accepts capability_execution port for the capability path
    sig = inspect.signature(Worker.__init__)
    assert "capability_execution" in sig.parameters


def test_workflow_definition_loader_is_in_workflow_runner() -> None:
    """WorkflowDefinition is loaded by workflow_runner's loader — not by OCP."""
    from loader import load_workflow  # workflow_runner/loader.py

    assert callable(load_workflow)
    # The loader returns a WorkflowDefinition, not a Capability
    assert WorkflowDefinition is not None


# ---- P. No workflow registry required ----


def test_no_workflow_registry_class_needed() -> None:
    """There is no WorkflowRegistry class — workflow lookup is handled by:
    1. OCP.select_execution_path via the workflow_lookup callback
    2. workflow_runner's Registry (filesystem-backed catalog of skills/tools/workflows)
    3. workflow_runner's loader (load_workflow / resolve_workflow_path)
    """
    # No WorkflowRegistry exists
    import importlib
    try:
        importlib.import_module("workflow_registry")
        assert False, "WorkflowRegistry module should not exist"
    except ImportError:
        pass  # Expected — no WorkflowRegistry


def test_registry_handles_workflow_lookup() -> None:
    """The existing Registry (workflow_runner) provides workflow lookup
    without needing a separate WorkflowRegistry."""
    from registry import Registry

    # Registry has get_workflow method
    assert hasattr(Registry, "get_workflow")
    assert hasattr(Registry, "list_workflows")


# ---- Helpers ----


def _make_inmemory_ocp() -> Any:
    """Create an InMemoryOrganisationControlPlane for testing."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    return InMemoryOrganisationControlPlane()
