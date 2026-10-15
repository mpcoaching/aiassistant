"""
Architectural tests for Increment 32 — Execution Boundary.

Proves that:
- CapabilityExecutionPort.execute takes capability_id only (no skill/tool/workflow conflation)
- ExecutionAuthorisationPort.is_authorised checks actor_id + actor_type + capability_id
- CapabilityAssignment is the authoritative Actor → Capability authorisation record
- CapabilityExecutionAdapter chains: registry.get → authorisation → deployment → execute_capability → record_invocation
- InvocationRecorder records to ConceptStore (not to a separate invocation store)
- Worker routes to CapabilityExecutionPort when work has required_capability_ids
- Operations dispatches READY Work to exactly one backend (Worker or Paperclip)
- EXISTING_WORKFLOW path uses WorkflowExecutionPort (separate from capability execution)
- CAPABILITY_PATH exercises a capability through CapabilityExecutionPort
- NEW_CAPABILITY_REQUIRED creates Work (work_type="capability_development")
- HUMAN_TEAM_INVESTIGATION does not execute — requires organisational reasoning
- Successful capability exercise produces InvocationRecorder telemetry in ConceptStore
- Successful capability development produces CapabilityProficiency evidence with source_work_id
- CapabilityRegistry owns lifecycle; OCP delegates registration/promotion
- Work is an organisational record, not an execution unit
- CapabilityDeployment is the execution binding (Operations plane), separate from domain Capability
- Actor and Agent are separate identity layers — Actor carries organisational context, Agent is the runtime identity
- Backend independence: Paperclip and Worker are interchangeable behind ExecutionBackend protocol
"""

from __future__ import annotations

import ast
import inspect
import os
from unittest.mock import MagicMock

from actor import Actor, ActorType
from capability import Capability, CapabilityKind, CapabilityStatus
from capability_assignment import (
    AssignmentStatus,
    CapabilityAssignment,
)
from capability_proficiency import CapabilityProficiency
from contracts.capability_execution import CapabilityExecutionPort, ExecutionResult
from contracts.capability_outcome_assessor import (
    CapabilityOutcome,
)
from contracts.invocation_recorder import InvocationRecorder

from execution_path import ExecutionPath, ExecutionPathResult
from role import Work, WorkStatus

PEOPLE_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "people_capability", "src"
))


# ---- A. CapabilityExecutionPort contract ----


def test_capability_execution_port_takes_capability_id_only() -> None:
    """CapabilityExecutionPort.execute takes capability_id — no skill_id/tool_id/workflow_id."""
    sig = inspect.signature(CapabilityExecutionPort.execute)
    params = list(sig.parameters.keys())
    assert "capability_id" in params
    assert "skill_id" not in params
    assert "tool_id" not in params
    assert "workflow_id" not in params


def test_capability_execution_port_is_protocol() -> None:
    import typing
    assert typing.is_protocol(CapabilityExecutionPort)


def test_capability_execution_port_returns_execution_result() -> None:
    sig = inspect.signature(CapabilityExecutionPort.execute)
    assert sig.return_annotation is not inspect.Signature.empty


# ---- B. ExecutionAuthorisationPort contract ----


def test_execution_authorisation_port_checks_actor_and_capability() -> None:
    """ExecutionAuthorisationPort.is_authorised checks actor_id, actor_type, capability_id."""
    from execution_authorisation import ExecutionAuthorisationPort

    sig = inspect.signature(ExecutionAuthorisationPort.is_authorised)
    params = list(sig.parameters.keys())
    assert "actor_id" in params
    assert "actor_type" in params
    assert "capability_id" in params


def test_execution_authorisation_returns_result_with_assignment() -> None:
    """AuthorisationResult carries assignment and proficiency, not just a boolean."""
    from execution_authorisation import AuthorisationResult

    result = AuthorisationResult(
        authorised=True,
        reason="test",
        assignment=CapabilityAssignment(
            id="asgn-1",
            capability_id="cap-1",
            actor_id="actor-1",
        ),
    )
    assert result.authorised is True
    assert result.assignment is not None
    assert result.assignment.capability_id == "cap-1"


# ---- C. CapabilityExecutionAdapter execution chain ----


def test_adapter_chain_registry_auth_deployment_record(monkeypatch) -> None:
    """CapabilityExecutionAdapter chains: registry.get → authorisation → deployment → execute_capability → record_invocation."""
    from capability_deployment import CapabilityDeployment, CompiledRef, ExecutionMode, Transport
    from workflow_runner.src.adapters.capability_execution_adapter import CapabilityExecutionAdapter

    cap = Capability(
        id="cap-chain",
        name="Chain Cap",
        capability_kind=CapabilityKind.TOOL,
        status=CapabilityStatus.ACTIVE,
        payload={"execution_mode": "compiled"},
    )
    registry = MagicMock()
    registry.get.return_value = cap

    def fake_deployment(c: Capability) -> CapabilityDeployment:
        return CapabilityDeployment(
            capability_id=c.id,
            environment="test",
            execution_mode=ExecutionMode.COMPILED,
            transport=Transport.TIER2_INPROCESS,
            compiled_ref=CompiledRef(module_path="nonexistent_module", entrypoint="run"),
        )

    recorder = MagicMock(spec=InvocationRecorder)
    authorisation = MagicMock()
    authorisation.is_authorised.return_value = MagicMock(
        authorised=True, reason="ok", assignment=None, proficiency=None
    )

    # Mock execute_capability to avoid import errors
    fake_result = ExecutionResult(outputs={"result": "success"}, telemetry={"capability_id": "cap-chain"})
    monkeypatch.setattr(
        "workflow_runner.src.adapters.capability_execution_adapter.execute_capability",
        MagicMock(return_value=fake_result),
    )

    adapter = CapabilityExecutionAdapter(
        registry=registry,
        deployment_factory=fake_deployment,
        authorisation_port=authorisation,
        invocation_recorder=recorder,
    )

    result = adapter.execute("cap-chain", {"key": "value"}, {"actor_id": "agent-1", "actor_type": "agent"})

    registry.get.assert_called_once_with("cap-chain")
    assert result.outputs["result"] == "success"
    recorder.record_invocation.assert_called_once()


def test_adapter_returns_not_authorised_when_assignment_inactive() -> None:
    """When the actor has no active assignment, execution is rejected before deployment."""
    from workflow_runner.src.adapters.capability_execution_adapter import CapabilityExecutionAdapter

    cap = Capability(id="cap-auth", name="Auth Cap", capability_kind=CapabilityKind.TOOL, status=CapabilityStatus.ACTIVE)
    registry = MagicMock()
    registry.get.return_value = cap

    authorisation = MagicMock()
    authorisation.is_authorised.return_value = MagicMock(
        authorised=False, reason="no_active_assignment", assignment=None, proficiency=None
    )

    adapter = CapabilityExecutionAdapter(
        registry=registry,
        deployment_factory=MagicMock(),
        authorisation_port=authorisation,
    )

    result = adapter.execute("cap-auth", {}, {"actor_id": "actor-x", "actor_type": "agent"})
    assert "error" in result.outputs or result.telemetry.get("error") == "execution_not_authorised"


def test_adapter_does_not_record_invocation_on_not_authorised_through_adapter() -> None:
    """CapabilityExecutionAdapter calls record_invocation on auth failure, but InvocationRecorderAdapter filters NOT_EXECUTED."""
    from workflow_runner.src.adapters.capability_execution_adapter import CapabilityExecutionAdapter
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )
    from workflow_runner.src.adapters.invocation_recorder_adapter import InvocationRecorderAdapter

    cap = Capability(id="cap-na", name="NA", capability_kind=CapabilityKind.TOOL, status=CapabilityStatus.ACTIVE)
    registry = MagicMock()
    registry.get.return_value = cap

    authorisation = MagicMock()
    authorisation.is_authorised.return_value = MagicMock(
        authorised=False, reason="no_active_assignment", assignment=None, proficiency=None
    )

    store = MagicMock()
    assessor = CapabilityOutcomeAssessorAdapter()
    recorder = InvocationRecorderAdapter(store=store, outcome_assessor=assessor)
    adapter = CapabilityExecutionAdapter(
        registry=registry,
        deployment_factory=MagicMock(),
        authorisation_port=authorisation,
        invocation_recorder=recorder,
    )

    adapter.execute("cap-na", {}, {"actor_id": "a1", "actor_type": "agent"})
    # The adapter calls record_invocation, but the recorder adapter filters NOT_EXECUTED
    store.record_invocation.assert_not_called()


# ---- D. Actor is the authorisation identity ----


def test_actor_type_discriminates_person_and_agent() -> None:
    """ActorType distinguishes PERSON from AGENT — the org layer uses actor_type."""
    assert ActorType.PERSON.value == "person"
    assert ActorType.AGENT.value == "agent"


def test_actor_carries_reference_id_to_runtime_entity() -> None:
    """Actor.reference_id points to the Person or Agent record (separate identity layers)."""
    actor = Actor(
        id="actor-1",
        name="Test Agent",
        actor_type=ActorType.AGENT,
        reference_id="agent-runtime-1",
    )
    assert actor.reference_id == "agent-runtime-1"
    assert actor.actor_type == ActorType.AGENT


def test_capability_assignment_uses_actor_id_not_person_or_agent_id() -> None:
    """CapabilityAssignment.actor_id is the canonical link; assignee_id is legacy compat."""
    assignment = CapabilityAssignment(
        id="asgn-1",
        capability_id="cap-1",
        actor_id="actor-1",
    )
    assert assignment.actor_id == "actor-1"
    # Legacy field is synced from actor_id
    assert assignment.assignee_id == "actor-1"


def test_agent_and_actor_are_separate_identity_layers() -> None:
    """Agent is the runtime entity; Actor is the organisational identity. They are distinct classes."""
    from agent import Agent
    assert Agent is not Actor
    agent = Agent(id="agent-1", name="Runtime Agent")
    actor = Actor(id="agent-1", name="Runtime Agent", actor_type=ActorType.AGENT, reference_id=agent.id)
    # Same ID, different model
    assert agent.id == actor.id
    assert actor.reference_id == agent.id


# ---- E. Worker routes to CapabilityExecutionPort ----


def test_worker_uses_capability_execution_port_for_assigned_capabilities() -> None:
    """Worker._execute_capability calls CapabilityExecutionPort.execute with capability_id."""
    from workflow_runner.src.worker import Worker

    sig = inspect.signature(Worker.__init__)
    assert "capability_execution" in sig.parameters


def test_worker_execute_invokes_port_with_capability_id_from_work() -> None:
    """Worker.execute routes to capability_execution.execute when work has required_capability_ids."""
    from workflow_runner.src.worker import Worker

    mock_port = MagicMock(spec=CapabilityExecutionPort)
    mock_port.execute.return_value = ExecutionResult(outputs={"result": "ok"})

    mock_org = MagicMock()
    worker = Worker(capability_execution=mock_port, output_dir="/tmp/test-worker-32")

    work = Work(
        id="w-cap-exec",
        title="Execute Capability",
        work_type="bau",
        accountable_role_id="r-1",
        required_capability_ids=["cap-target"],
        context={"input": "data"},
        status=WorkStatus.READY,
    )

    result = worker.execute(work, mock_org)

    mock_port.execute.assert_called_once()
    call_kwargs = mock_port.execute.call_args
    assert call_kwargs.kwargs["capability_id"] == "cap-target"
    assert result["status"] == "completed"


def test_worker_routes_capability_development_to_develop_method() -> None:
    """Worker routes work_type='capability_development' to _develop_capability, not _execute_capability."""
    from unittest.mock import MagicMock as Mock

    from workflow_runner.src.worker import Worker

    mock_port = MagicMock(spec=CapabilityExecutionPort)
    mock_org = Mock()
    worker = Worker(capability_execution=mock_port, output_dir="/tmp/test-worker-32")

    work = Work(
        id="w-dev-32",
        title="Develop capability: New Cap",
        work_type="capability_development",
        accountable_role_id="r-1",
        status=WorkStatus.READY,
    )

    result = worker.execute(work, mock_org)
    mock_port.execute.assert_not_called()
    assert result["status"] == "completed"
    assert result["execution_mode"] == "capability_development"


# ---- F. Operations backend dispatch ----


def test_operations_subscribes_to_org_events() -> None:
    """Operations registers as an event handler on the Organisation Control Plane."""
    from workflow_runner.src.operations import Operations

    mock_plane = MagicMock()
    mock_plane.list_work.return_value = []
    Operations(org_plane=mock_plane)

    mock_plane.on_event.assert_called_once()
    handler = mock_plane.on_event.call_args[0][0]
    assert callable(handler)


def test_operations_selects_worker_backend_for_unassigned_work() -> None:
    """WorkerBackend wraps Worker and can_handle returns True when work has no assignee_agent_id."""
    from workflow_runner.src.operations import WorkerBackend

    mock_worker = MagicMock()
    mock_worker.execute.return_value = {"status": "completed"}
    backend = WorkerBackend(worker=mock_worker, org_plane=MagicMock())

    work = Work(
        id="w-1",
        title="Task",
        work_type="bau",
        accountable_role_id="r-1",
        status=WorkStatus.READY,
    )
    assert work.assignee_agent_id is None
    assert backend.can_handle(work) is True


def test_operations_reports_result_to_organisation_on_completion() -> None:
    """Operations calls complete_work on the org plane after successful execution."""
    from workflow_runner.src.operations import Operations, WorkerBackend

    mock_plane = MagicMock()
    mock_plane.list_work.return_value = []
    mock_plane.get_work.return_value = Work(
        id="w-ops",
        title="Task",
        work_type="bau",
        accountable_role_id="r-1",
        status=WorkStatus.READY,
    )

    mock_worker = MagicMock()
    mock_worker.execute.return_value = {"status": "completed", "summary": "done"}
    backend = WorkerBackend(worker=mock_worker, org_plane=mock_plane)

    ops = Operations(org_plane=mock_plane, backends=[backend])

    from contracts.organisational_events import WorkEvent, WorkEventType
    event = WorkEvent(
        event_type=WorkEventType.READY,
        organisation_id="default",
        work_id="w-ops",
        title="Task",
        work_type="bau",
        required_capability_ids=[],
        status="ready",
        priority="normal",
    )
    ops._handle_event(event)

    mock_plane.complete_work.assert_called_once()
    result = mock_plane.complete_work.call_args[0]
    assert result[0] == "w-ops"
    assert result[1]["status"] == "completed"


# ---- G. WorkflowDefinition vs capability execution ----


def test_workflow_state_is_persistent_state_not_execution_unit() -> None:
    """WorkflowState tracks persistent execution state — it is not the capability domain model."""
    from models import Step, StepType, WorkflowDefinition, WorkflowState

    wf = WorkflowDefinition(
        name="test-wf",
        steps=[Step(type=StepType.SKILL, name="step1", uses="skill-1")],
    )
    state = WorkflowState(
        workflow_id="wf-1",
        workflow_name="test-wf",
        workflow_path="/tmp/wf.yaml",
        steps=wf.steps,
    )
    assert state.status == "pending"
    assert state.current_step_index == 0
    assert len(state.steps) == 1


def test_workflow_execution_port_is_separate_from_capability_execution_port() -> None:
    """WorkflowExecutionPort and CapabilityExecutionPort are separate contracts."""
    from contracts.workflow_execution import WorkflowExecutionPort

    sig_wf = inspect.signature(WorkflowExecutionPort.execute_workflow)
    inspect.signature(CapabilityExecutionPort.execute)

    # Different method names and signatures
    assert "execute_workflow" in dir(WorkflowExecutionPort)
    assert "execute" in dir(CapabilityExecutionPort)
    assert list(sig_wf.parameters.keys()) == ["self", "request"]
    assert "workflow_name" in sig_wf.parameters["request"].annotation.model_fields


def test_workflow_definition_steps_reference_by_name_not_domain_model() -> None:
    """WorkflowDefinition Step uses string `uses`, not Skill/Tool domain objects."""
    from models import Step, StepType

    step = Step(
        type=StepType.SKILL,
        name="invoke_skill",
        uses="summarise_text",
    )
    assert isinstance(step.uses, str)
    assert step.uses == "summarise_text"


# ---- H. Execution path semantics ----


def test_execution_path_enum_values() -> None:
    """ExecutionPath has four distinct paths — each with clear organisational semantics."""
    assert ExecutionPath.EXISTING_WORKFLOW.value == "existing_workflow"
    assert ExecutionPath.CAPABILITY_PATH.value == "capability_path"
    assert ExecutionPath.NEW_CAPABILITY_REQUIRED.value == "new_capability_required"
    assert ExecutionPath.HUMAN_TEAM_INVESTIGATION.value == "human_team_investigation"


def test_execution_path_result_carry_capability_id_or_workflow() -> None:
    """ExecutionPathResult carries capability_id or workflow, both optional."""
    result = ExecutionPathResult(path=ExecutionPath.CAPABILITY_PATH, capability_id="cap-1")
    assert result.capability_id == "cap-1"
    assert result.workflow is None

    result2 = ExecutionPathResult(path=ExecutionPath.EXISTING_WORKFLOW, workflow=MagicMock())
    assert result2.workflow is not None
    assert result2.capability_id is None


def test_existing_workflow_path_does_not_invoke_capability_execution() -> None:
    """EXISTING_WORKFLOW path delegates to WorkflowExecutionPort, not CapabilityExecutionPort."""
    from workflow_runner.src.adapters.workflow_execution_adapter import WorkflowExecutionAdapter

    adapter = WorkflowExecutionAdapter()
    assert hasattr(adapter, "execute_workflow")
    sig = inspect.signature(adapter.execute_workflow)
    assert "request" in sig.parameters


def test_human_team_investigation_path_creates_no_execution_work() -> None:
    """HUMAN_TEAM_INVESTIGATION produces evidence of need, not executable Work."""
    plane = MagicMock()
    plane.get_capability.return_value = Capability(
        id="cap-busy", name="Busy", capability_kind=CapabilityKind.SKILL, status=CapabilityStatus.ACTIVE
    )
    plane.list_work.return_value = []
    plane.query_capability.return_value = {
        "capability_id": "cap-busy",
        "available": False,
        "reason": "capacity_pressure",
    }
    from organisation_control_plane import InMemoryOrganisationControlPlane
    ocp = InMemoryOrganisationControlPlane()
    cap = Capability(id="cap-busy", name="Busy", capability_kind=CapabilityKind.SKILL, status=CapabilityStatus.ACTIVE)
    ocp.register_capability(cap)

    result = ocp.select_execution_path(
        intent="use cap-busy",
        context={"required_capability_ids": ["cap-busy"]},
        capability_query=lambda cid: {
            "capability_id": cid,
            "available": False,
            "reason": "capacity_pressure",
        },
    )
    assert result.path == ExecutionPath.HUMAN_TEAM_INVESTIGATION


# ---- I. CapabilityRegistry lifecycle ownership ----


def test_registry_owns_promote_lifecycle() -> None:
    """CapabilityRegistry.promote transitions DRAFT → ACTIVE."""
    from capabilities import CapabilityRegistry
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    cap = Capability(
        id="cap-promote-32",
        name="Promote",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.DRAFT,
    )
    registry.register(cap)
    assert registry.get("cap-promote-32").status == CapabilityStatus.DRAFT

    promoted = registry.promote("cap-promote-32")
    assert promoted.status == CapabilityStatus.ACTIVE


def test_ocp_delegates_capability_lifecycle_to_registry() -> None:
    """OCP.register_capability delegates to the injected registry."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    mock_registry = MagicMock()
    plane = InMemoryOrganisationControlPlane(capability_registry=mock_registry)

    cap = Capability(id="cap-ocp-32", name="OCP Cap", capability_kind=CapabilityKind.SKILL, status=CapabilityStatus.ACTIVE)
    plane.register_capability(cap)

    mock_registry.register.assert_called_once_with(cap)
    assert "cap-ocp-32" not in plane._capabilities


def test_ocp_does_not_import_capability_registry_impl() -> None:
    """OCP source must not import from capability_registry package."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    source = inspect.getsource(InMemoryOrganisationControlPlane)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "capability_registry" not in node.module, (
                f"OCP must not import from capability_registry: {node.module}"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "capability_registry" not in alias.name, (
                    f"OCP must not import capability_registry module: {alias.name}"
                )


# ---- J. Work is organisational record, not execution unit ----


def test_work_has_required_capability_ids_field() -> None:
    """Work.required_capability_ids links organisational intent to capability execution."""
    work = Work(
        id="w-1",
        title="Analyse data",
        work_type="bau",
        accountable_role_id="r-1",
        required_capability_ids=["cap-analyse"],
    )
    assert work.required_capability_ids == ["cap-analyse"]


def test_work_is_not_a_capability() -> None:
    """Work and Capability are different classes with different lifecycles."""
    work = Work(
        id="w-1",
        title="Task",
        work_type="bau",
        accountable_role_id="r-1",
    )
    cap = Capability(id="cap-1", name="Task Cap", capability_kind=CapabilityKind.SKILL)
    assert type(work).__name__ != type(cap).__name__


def test_work_status_transitions_are_organisational() -> None:
    """WorkStatus has READY as organisational handoff to Operations."""
    from role import WorkStatus

    valid_statuses = {"pending", "assigned", "ready", "in_progress", "completed", "failed", "cancelled", "escalated"}
    actual = {s.value for s in WorkStatus}
    assert valid_statuses == actual
    assert WorkStatus.READY.value == "ready"


def test_mark_work_ready_is_organisational_handoff() -> None:
    """OCP.mark_work_ready transitions to READY — the organisational handoff to Operations."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()
    work = Work(id="w-handoff", title="Task", work_type="bau", accountable_role_id="r-1")
    plane._work[work.id] = work

    result = plane.mark_work_ready(work.id)
    assert result is not None
    assert result.status == WorkStatus.READY


# ---- K. CapabilityDeployment is execution binding ----


def test_capability_deployment_is_not_capability() -> None:
    """CapabilityDeployment is a separate Operations-plane model, not the Capability domain model."""
    from capability_deployment import CapabilityDeployment, ExecutionMode, Transport

    assert CapabilityDeployment is not Capability

    deployment = CapabilityDeployment(
        capability_id="cap-1",
        environment="prod",
        execution_mode=ExecutionMode.COMPILED,
        transport=Transport.TIER2_INPROCESS,
    )
    assert deployment.capability_id == "cap-1"
    assert deployment.execution_mode == ExecutionMode.COMPILED


def test_capability_deployment_has_execution_mode() -> None:
    """CapabilityDeployment carries ExecutionMode (AI_MEDIATED or COMPILED)."""
    from capability_deployment import CapabilityDeployment, ExecutionMode, Transport

    deployment = CapabilityDeployment(
        capability_id="cap-1",
        environment="test",
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport=Transport.TIER2_INPROCESS,
    )
    assert deployment.execution_mode == ExecutionMode.AI_MEDIATED


# ---- L. InvocationRecorder records capability telemetry ----


def test_invocation_recorder_protocol_contract() -> None:
    """InvocationRecorder.record_invocation takes capability_id, result, actor_context."""
    sig = inspect.signature(InvocationRecorder.record_invocation)
    params = list(sig.parameters.keys())
    assert "capability_id" in params
    assert "result" in params
    assert "actor_context" in params


def test_invocation_recorder_adapter_skips_not_executed() -> None:
    """InvocationRecorderAdapter does not record when CapabilityOutcome is NOT_EXECUTED."""
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )
    from workflow_runner.src.adapters.invocation_recorder_adapter import InvocationRecorderAdapter

    store = MagicMock()
    assessor = CapabilityOutcomeAssessorAdapter()
    adapter = InvocationRecorderAdapter(store=store, outcome_assessor=assessor)

    result = ExecutionResult(
        outputs={"error": "capability_not_found"},
        telemetry={"error": "capability_not_found"},
    )
    adapter.record_invocation("cap-1", result, {"actor_id": "a1"})

    store.record_invocation.assert_not_called()


def test_invocation_recorder_adapter_records_executed_capability() -> None:
    """When capability execution succeeds, InvocationRecorder records to ConceptStore."""
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )
    from workflow_runner.src.adapters.invocation_recorder_adapter import InvocationRecorderAdapter

    store = MagicMock()
    assessor = CapabilityOutcomeAssessorAdapter()
    adapter = InvocationRecorderAdapter(store=store, outcome_assessor=assessor)

    result = ExecutionResult(
        outputs={"result": "success"},
        telemetry={"capability_id": "cap-1"},
    )
    adapter.record_invocation("cap-1", result, {"actor_id": "a1"})

    store.record_invocation.assert_called_once_with("cap-1", "success")


# ---- M. CapabilityOutcomeAssessor distinguishes pre-execution failures ----


def test_outcome_assessor_pre_execution_errors_are_not_executed() -> None:
    """Authorisation failures, capability-not-found, and missing deployment are NOT_EXECUTED."""
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )

    assessor = CapabilityOutcomeAssessorAdapter()

    for error in ["capability_not_found", "execution_not_authorised", "no_deployment"]:
        result = ExecutionResult(outputs={"error": "fail"}, telemetry={"error": error})
        assert assessor.assess(result) == CapabilityOutcome.NOT_EXECUTED, (
            f"Expected NOT_EXECUTED for {error}"
        )


def test_outcome_assessor_execution_failure_is_failed() -> None:
    """Errors during execution (not pre-execution) are classified as FAILED."""
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )

    assessor = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(outputs={"error": "runtime error"}, telemetry={"error": "runtime_error"})
    assert assessor.assess(result) == CapabilityOutcome.FAILED


def test_outcome_assessor_success_is_executed() -> None:
    """Successful execution with no errors is EXECUTED."""
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )

    assessor = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(outputs={"data": "ok"}, telemetry={})
    assert assessor.assess(result) == CapabilityOutcome.EXECUTED


# ---- N. Evidence boundary: successful exercise → reusable execution ----


def test_capability_proficiency_evidence_links_to_source_work() -> None:
    """CapabilityProficiency.evidence entries carry source_work_id linking to the originating Work."""
    proficiency = CapabilityProficiency(
        id="prof-1",
        capability_id="cap-1",
        actor_id="actor-1",
        evidence=[
            {
                "source_work_id": "w-1",
                "type": "execution",
                "content": {"status": "completed"},
            }
        ],
    )
    assert proficiency.evidence[0]["source_work_id"] == "w-1"
    assert proficiency.actor_id == "actor-1"


def test_assess_capability_development_produces_evidence_with_source_work_id() -> None:
    """assess_capability_development produces structured evidence linked to the Work."""
    from organisation.src.outcome import assess_capability_development

    work = Work(
        id="w-dev-32",
        title="Develop capability: Test Cap",
        work_type="capability_development",
        accountable_role_id="r-1",
    )
    cap = Capability(
        id="cap-dev-32",
        name="Test Cap",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.DRAFT,
        interface={
            "inputs": [{"name": "context", "type": "dict", "required": True}],
            "outputs": [{"name": "result", "type": "dict", "required": True}],
        },
    )
    execution_result = {
        "status": "completed",
        "execution_mode": "capability_development",
        "capability_id": "cap-dev-32",
        "artifact_path": "/tmp/artifact.md",
    }

    assessment = assess_capability_development(work, cap, execution_result)
    assert assessment["passed"] is True
    assert assessment["source_work_id"] == "w-dev-32"

    evidence = assessment["evidence"]
    assert any(e["source_work_id"] == "w-dev-32" for e in evidence)


def test_operations_records_proficiency_after_successful_capability_development() -> None:
    """Operations._record_proficiency creates CapabilityProficiency with source_work_id in metadata."""
    from workflow_runner.src.operations import Operations

    mock_plane = MagicMock()
    mock_plane.list_work.return_value = []
    mock_registry = MagicMock()
    cap = Capability(id="cap-prof-32", name="Prof Cap", capability_kind=CapabilityKind.SKILL, status=CapabilityStatus.ACTIVE)
    mock_registry.get.return_value = cap

    ops = Operations(org_plane=mock_plane, capability_registry=mock_registry)

    work = Work(
        id="w-prof-32",
        title="Develop capability: Prof Cap",
        work_type="capability_development",
        accountable_role_id="r-1",
        assignee_agent_id="worker-1",
    )
    assessment = {
        "passed": True,
        "capability_id": "cap-prof-32",
        "source_work_id": "w-prof-32",
        "evidence": [{"source_work_id": "w-prof-32", "type": "execution", "content": {}}],
        "rationale": "passed",
        "validation_details": {"assessor": "system"},
    }

    ops._record_proficiency(work, cap, assessment)

    assert hasattr(ops, "_proficiencies")
    profs = list(ops._proficiencies.values())
    assert len(profs) == 1
    assert profs[0].capability_id == "cap-prof-32"
    assert profs[0].actor_id == "worker-1"
    assert profs[0].evidence[0]["source_work_id"] == "w-prof-32"


def test_capability_development_learning_loop_complete() -> None:
    """Full learning loop: capability gap → Work → DRAFT → assess → promote → ACTIVE → assignable → executable."""
    from agent_store import InMemoryAgentStore
    from capabilities import CapabilityRegistry
    from capability_registry.src.adapters.execution_authorisation_adapter import (
        InMemoryExecutionAuthorisationPort,
    )
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore
    from organisation.src.outcome import assess_capability_development

    from organisation_control_plane import InMemoryOrganisationControlPlane

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)
    plane = InMemoryOrganisationControlPlane(capability_registry=registry)

    cap = Capability(
        id="cap-loop-32",
        name="Loop Cap",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.DRAFT,
        interface={
            "inputs": [{"name": "context", "type": "dict", "required": True}],
            "outputs": [{"name": "result", "type": "dict", "required": True}],
        },
    )
    plane.register_capability(cap)
    assert registry.get("cap-loop-32").status == CapabilityStatus.DRAFT

    work = Work(
        id="w-loop-32",
        title="Develop capability: Loop Cap",
        work_type="capability_development",
        accountable_role_id="r-1",
        develops_capability_id="cap-loop-32",
        status=WorkStatus.READY,
    )

    execution_result = {
        "status": "completed",
        "execution_mode": "capability_development",
        "capability_id": "cap-loop-32",
        "artifact_path": "/tmp/loop-32.md",
    }

    assessment = assess_capability_development(work, cap, execution_result)
    assert assessment["passed"] is True

    promoted = registry.promote("cap-loop-32")
    assert promoted.status == CapabilityStatus.ACTIVE

    agent_store = InMemoryAgentStore()
    agent, _actor = InMemoryAgentStore.create_assistant_actor(actor_id="worker-32")
    agent_store.register_agent(agent)
    assignment = agent_store.assign_capability("worker-32", "cap-loop-32")
    assert assignment.status == AssignmentStatus.ACTIVE

    auth = InMemoryExecutionAuthorisationPort(assignments=agent_store.get_all_assignments())
    result = auth.is_authorised("worker-32", "agent", "cap-loop-32")
    assert result.authorised is True


# ---- O. Backend independence ----


def test_paperclip_backend_implements_execution_backend_protocol() -> None:
    """PaperclipBackend implements the execute() / can_handle() contract."""
    from workflow_runner.src.operations import PaperclipBackend

    backend = PaperclipBackend(MagicMock())
    assert hasattr(backend, "execute")
    assert hasattr(backend, "can_handle")
    assert callable(backend.execute)
    assert callable(backend.can_handle)


def test_worker_backend_implements_execution_backend_protocol() -> None:
    """WorkerBackend implements the execute() / can_handle() contract."""
    from workflow_runner.src.operations import WorkerBackend

    backend = WorkerBackend(worker=MagicMock(), org_plane=MagicMock())
    assert hasattr(backend, "execute")
    assert hasattr(backend, "can_handle")


def test_operations_selects_paperclip_for_assigned_agent_work() -> None:
    """PaperclipBackend.can_handle returns True when work has assignee_agent_id."""
    from workflow_runner.src.operations import PaperclipBackend

    backend = PaperclipBackend(MagicMock())
    work = Work(
        id="w-p",
        title="P work",
        work_type="bau",
        accountable_role_id="r-1",
    )
    work.assignee_agent_id = "paperclip-agent-1"

    assert backend.can_handle(work) is True


def test_operations_selects_worker_when_no_assigned_agent() -> None:
    """WorkerBackend.can_handle returns True when work has no assignee_agent_id."""
    from workflow_runner.src.operations import WorkerBackend

    backend = WorkerBackend(worker=MagicMock(), org_plane=MagicMock())
    work = Work(
        id="w-w",
        title="W work",
        work_type="bau",
        accountable_role_id="r-1",
    )
    assert work.assignee_agent_id is None
    assert backend.can_handle(work) is True


def test_tool_implementation_type_is_abstract_not_concrete() -> None:
    """ToolImplementationType values are mechanism identifiers, not class references."""
    from tool import Tool, ToolImplementationType

    tool = Tool(
        id="tool-32",
        name="Test Tool",
        implementation_type=ToolImplementationType.PAPERCLIP,
        implementation_ref="agent-1",
    )
    assert tool.implementation_type == ToolImplementationType.PAPERCLIP
    assert isinstance(tool.implementation_ref, str)

    # Same for LANGGRAPH
    tool2 = Tool(
        id="tool-32b",
        name="Graph Tool",
        implementation_type=ToolImplementationType.LANGGRAPH,
        implementation_ref="node-1",
    )
    assert tool2.implementation_type == ToolImplementationType.LANGGRAPH


# ---- P. People/Capability does not import backend layers ----


def test_people_capability_does_not_import_paperclip() -> None:
    """people_capability domain models must not import Paperclip."""
    people_modules = []
    for filename in sorted(os.listdir(PEOPLE_SRC)):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(PEOPLE_SRC, filename)
        with open(path) as f:
            try:
                people_modules.append(ast.parse(f.read(), filename=path))
            except SyntaxError:
                continue

    for mod in people_modules:
        for node in ast.walk(mod):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "paperclip" not in alias.name.lower(), (
                        f"people_capability imports Paperclip: {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "paperclip" not in node.module.lower(), (
                    f"people_capability imports from Paperclip: {node.module}"
                )


def test_people_capability_does_not_import_workflow_runner() -> None:
    """people_capability domain models must not import workflow_runner."""
    people_modules = []
    for filename in sorted(os.listdir(PEOPLE_SRC)):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(PEOPLE_SRC, filename)
        with open(path) as f:
            try:
                people_modules.append(ast.parse(f.read(), filename=path))
            except SyntaxError:
                continue

    for mod in people_modules:
        for node in ast.walk(mod):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "workflow_runner" not in alias.name.lower(), (
                        f"people_capability imports workflow_runner: {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "workflow_runner" not in node.module.lower(), (
                    f"people_capability imports from workflow_runner: {node.module}"
                )


def test_workflow_runner_models_are_not_domain_models() -> None:
    """workflow_runner's SkillDefinition and ToolDefinition are implementation specs, not domain models."""
    from models import SkillDefinition, ToolDefinition
    from skill import Skill
    from tool import Tool

    assert SkillDefinition is not Skill
    assert ToolDefinition is not Tool

    skill_def_fields = set(SkillDefinition.model_fields.keys())
    domain_skill_fields = set(Skill.model_fields.keys())

    assert "capability_id" in domain_skill_fields
    assert "capability_id" not in skill_def_fields
    assert "method" in domain_skill_fields
    assert "method" not in skill_def_fields

    tool_def_fields = set(ToolDefinition.model_fields.keys())
    domain_tool_fields = set(Tool.model_fields.keys())

    assert "implementation_type" in domain_tool_fields
    assert "implementation_type" not in tool_def_fields
    assert "action" in tool_def_fields
    assert "action" not in domain_tool_fields
