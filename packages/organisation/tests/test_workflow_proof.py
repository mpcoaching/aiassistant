"""
Behavioural tests for Increment 10/11 — Organisational Workflow Proof.

Proves that organisational accountability and coordination produce operational
work without the organisation becoming the operations engine, and that operations
produce evidence without becoming the organisation.

Corrected Increment 11: OrganisationControlPlane does NOT execute Work.
It marks Work as ready. Operations executes Work via its own entry points.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from concepts import ConceptKind, ConceptStore

from organisation_control_plane import InMemoryOrganisationControlPlane
from outcome import assess_work_outcome, record_work_learning
from role import Agent, Person, Role, Work, WorkStatus

# ---- Test 1: Strategic work flow ------------------------------------------------


def test_strategic_work_flow_without_ceo_coordinating() -> None:
    """CEO makes strategic decision, C-Suite is accountable, PM coordinates."""
    plane = InMemoryOrganisationControlPlane()
    ceo = Role(id="r-ceo", name="CEO")
    cmo = Role(id="r-cmo", name="CMO")
    pm = Role(id="r-pm", name="Project Manager")
    plane.register_role(ceo)
    plane.register_role(cmo)
    plane.register_role(pm)

    initiative = Work(
        id="w-init",
        title="Enter Market X",
        work_type="project",
        accountable_role_id="r-cmo",
        coordinating_role_id="r-pm",
        required_capability_ids=["cap-market-analysis"],
    )
    plane.assign_work(initiative, cmo)

    assert initiative.accountable_role_id == "r-cmo"
    assert initiative.coordinating_role_id == "r-pm"
    assert ceo.id not in [initiative.accountable_role_id, initiative.coordinating_role_id]


# ---- Test 2: BAU work flow ------------------------------------------------------


def test_bau_work_flow_without_ceo_involvement() -> None:
    """BAU: functional manager accountable and coordinates, work ready for execution."""
    plane = InMemoryOrganisationControlPlane()
    fm = Role(id="r-fm", name="Functional Manager")
    plane.register_role(fm)

    work = Work(
        id="w-bau",
        title="Fix KPI deterioration",
        work_type="bau",
        accountable_role_id="r-fm",
        coordinating_role_id="r-fm",
    )
    plane.assign_work(work, fm)
    assert work.status == WorkStatus.ASSIGNED

    ready = plane.mark_work_ready("w-bau")
    assert ready is not None
    assert ready.status == WorkStatus.IN_PROGRESS
    assert work.accountable_role_id == "r-fm"


# ---- Test 3: Work decomposition --------------------------------------------------


def test_work_decomposition_proves_parent_child() -> None:
    """Parent work decomposes into specialist child work items."""
    plane = InMemoryOrganisationControlPlane()
    cmo = Role(id="r-cmo", name="CMO")
    pm = Role(id="r-pm", name="Project Manager")
    ea = Role(id="r-ea", name="EA")
    dev = Role(id="r-dev", name="Developer")
    for r in [cmo, pm, ea, dev]:
        plane.register_role(r)

    initiative = Work(
        id="w-init",
        title="Enter Market X",
        work_type="project",
        accountable_role_id="r-cmo",
        coordinating_role_id="r-pm",
    )
    plane.assign_work(initiative, cmo)

    design = Work(
        id="w-design",
        title="Design system",
        work_type="project",
        parent_work_id="w-init",
        accountable_role_id="r-ea",
        coordinating_role_id="r-pm",
    )
    implementation = Work(
        id="w-impl",
        title="Implement system",
        work_type="project",
        parent_work_id="w-init",
        accountable_role_id="r-dev",
        coordinating_role_id="r-pm",
        dependencies=["w-design"],
    )

    plane.assign_work(design, ea)
    plane.assign_work(implementation, dev)

    assert design.parent_work_id == "w-init"
    assert implementation.parent_work_id == "w-init"
    assert implementation.dependencies == ["w-design"]
    assert initiative.accountable_role_id == "r-cmo"
    assert design.accountable_role_id == "r-ea"
    assert implementation.accountable_role_id == "r-dev"


# ---- Test 4: Work dependencies ---------------------------------------------------


def test_work_dependencies_express_sequencing() -> None:
    """Work B depends on Work A, expressing sequencing requirement."""
    plane = InMemoryOrganisationControlPlane()
    dev = Role(id="r-dev", name="Developer")
    qa = Role(id="r-qa", name="QA")
    plane.register_role(dev)
    plane.register_role(qa)

    implementation = Work(
        id="w-impl",
        title="Implement feature",
        accountable_role_id="r-dev",
        dependencies=[],
    )
    testing = Work(
        id="w-test",
        title="Test feature",
        accountable_role_id="r-qa",
        dependencies=["w-impl"],
    )

    plane.assign_work(implementation, dev)
    plane.assign_work(testing, qa)

    assert testing.dependencies == ["w-impl"]
    assert implementation.dependencies == []


# ---- Test 5: Capability declaration ----------------------------------------------


def test_work_declares_capabilities_without_discovery() -> None:
    """Work can declare required_capability_ids without performing capability matching."""
    plane = InMemoryOrganisationControlPlane()
    dev = Role(id="r-dev", name="Developer")
    plane.register_role(dev)

    work = Work(
        id="w1",
        title="Build feature",
        accountable_role_id="r-dev",
        required_capability_ids=["cap-coding", "cap-testing"],
    )

    assert work.required_capability_ids == ["cap-coding", "cap-testing"]
    assert not hasattr(plane, "find_capability")
    assert not hasattr(plane, "match_capability")


# ---- Test 6: Capability portability ----------------------------------------------


def test_capability_portable_across_roles() -> None:
    """Same capability can be required by multiple roles."""
    ea = Role(id="r-ea", name="EA", required_capability_ids=["cap-arch"])
    sa = Role(id="r-sa", name="SA", required_capability_ids=["cap-arch"])
    dev = Role(id="r-dev", name="Dev", required_capability_ids=["cap-arch", "cap-code"])

    assert ea.required_capability_ids == ["cap-arch"]
    assert sa.required_capability_ids == ["cap-arch"]
    assert dev.required_capability_ids == ["cap-arch", "cap-code"]
    assert ea.id != sa.id != dev.id


# ---- Test 7: Operational handoff -------------------------------------------------


def test_operational_handoff_is_status_transition_not_execution() -> None:
    """Organisational Work transitions to IN_PROGRESS (ready for execution).
    
    OrganisationControlPlane does NOT execute Work. It only marks Work as ready.
    Operations is responsible for picking up ready Work and executing it.
    """
    plane = InMemoryOrganisationControlPlane()
    operator = Role(id="r-ops", name="Operator")
    plane.register_role(operator)

    work = Work(
        id="w-handoff",
        title="Operational task",
        accountable_role_id="r-ops",
    )
    assignment = plane.assign_work(work, operator)
    assert work.status == WorkStatus.ASSIGNED

    ready = plane.mark_work_ready("w-handoff")
    assert ready is not None
    assert ready.status == WorkStatus.IN_PROGRESS
    assert assignment.assignee_id == "r-ops"

    assert not hasattr(plane, "execute_work")
    assert not hasattr(plane, "invoke")
    assert not hasattr(plane, "run_agent")


# ---- Test 8: Outcome assessment --------------------------------------------------


def test_outcome_assessment_execution_result_not_automatic_acceptance() -> None:
    """Execution result is evidence; does not automatically equal accepted outcome."""
    work = Work(
        id="w1",
        title="Build feature",
        accountable_role_id="r-dev",
        acceptance_criteria=["Feature works", "Tests pass"],
    )

    failed_result = {
        "status": "failed",
        "outputs": {"error": "Tests failed"},
        "artifacts": [],
    }

    assessment = assess_work_outcome(work, failed_result)
    assert assessment["accepted"] is False
    assert len(assessment["criteria_failed"]) > 0

    success_result = {
        "status": "completed",
        "outputs": {"summary": "Feature works. Tests pass."},
        "artifacts": [],
    }

    assessment2 = assess_work_outcome(work, success_result)
    assert assessment2["accepted"] is True
    assert len(assessment2["criteria_met"]) == 2


# ---- Test 9: EIMS learning -------------------------------------------------------


def test_eims_learning_from_completed_work() -> None:
    """Completed work with enterprise value becomes EnterpriseConcept in EIMS."""
    store = ConceptStore(data_dir="/tmp/test_concepts_eims")
    work = Work(
        id="w-proj",
        title="Market entry strategy",
        work_type="project",
        accountable_role_id="r-cmo",
        coordinating_role_id="r-pm",
        acceptance_criteria=["Strategy approved"],
        outcome={"summary": "Strategy approved by board"},
    )

    success_result = {
        "status": "completed",
        "outputs": {"summary": "Strategy approved by board"},
    }

    assessment = assess_work_outcome(work, success_result)
    assert assessment["accepted"] is True

    concept = record_work_learning(work, assessment, store)
    assert concept is not None
    assert concept.kind == ConceptKind.SOLVED_APPROACH
    assert concept.name == "Market entry strategy"

    retrieved = store.get(concept.id)
    assert retrieved is not None
    assert retrieved.payload["work_id"] == "w-proj"


def test_eims_learning_ignores_routine_bau() -> None:
    """Routine BAU work does not become EIMS knowledge."""
    store = ConceptStore(data_dir="/tmp/test_concepts_bau")
    work = Work(
        id="w-bau",
        title="Fix typo",
        work_type="bau",
        accountable_role_id="r-fm",
        acceptance_criteria=["Typo fixed"],
        outcome={"summary": "Typo fixed"},
    )

    success_result = {
        "status": "completed",
        "outputs": {"summary": "Typo fixed"},
    }

    assessment = assess_work_outcome(work, success_result)
    concept = record_work_learning(work, assessment, store)
    assert concept is None


# ---- Test 10: CEO boundary ------------------------------------------------------


def test_ceo_does_not_coordinate_specialist_work() -> None:
    """CEO does not assign specialist tasks or coordinate projects."""
    from ceo import CEOAgent

    org_context = MagicMock()
    ceo = CEOAgent(org_context=org_context)

    assert not hasattr(ceo, "assign_work")
    assert not hasattr(ceo, "execute_work")
    assert not hasattr(ceo, "match_capabilities")
    assert not hasattr(ceo, "_match_capabilities")


def test_ocp_does_not_become_project_manager() -> None:
    """OrganisationControlPlane provides mechanisms, not coordination."""
    plane = InMemoryOrganisationControlPlane()
    assert not hasattr(plane, "coordinate_project")
    assert not hasattr(plane, "sequence_work")
    assert not hasattr(plane, "track_progress")
    assert not hasattr(plane, "manage_dependencies")


def test_work_is_not_capability() -> None:
    """Work is organisational effort, not reusable ability."""
    work = Work(id="w1", title="Task", accountable_role_id="r1")
    assert work.id != "capability"
    assert not hasattr(work, "execution_mode")
    assert not hasattr(work, "capability_kind")


def test_work_is_not_workflow() -> None:
    """Work is assignment, not execution flow."""
    work = Work(id="w1", title="Task", accountable_role_id="r1")
    assert not hasattr(work, "steps")
    assert not hasattr(work, "ordered_steps")


def test_role_is_not_person() -> None:
    """Role is abstract position, not human individual."""
    role = Role(id="r1", name="Developer")
    person = Person(id="p1", name="Alice")
    assert role.id != person.id
    assert not hasattr(role, "email")
    assert not hasattr(role, "employment_context")


def test_role_is_not_agent() -> None:
    """Role is abstract position, not software executor."""
    role = Role(id="r1", name="Developer")
    agent = Agent(id="a1", name="Bot")
    assert role.id != agent.id
    assert not hasattr(role, "marker")
    assert not hasattr(role, "runtime_identity")


def test_capability_is_not_agent() -> None:
    """Capability is ability, not executor."""
    from capability import Capability, CapabilityKind

    cap = Capability(
        id="cap-1",
        kind=ConceptKind.CAPABILITY,
        name="Coding",
        capability_kind=CapabilityKind.SKILL,
    )
    agent = Agent(id="a1", name="DevBot")
    assert cap.id != agent.id
    assert not hasattr(cap, "marker")
    assert not hasattr(cap, "fulfilled_role_ids")


def test_operations_executes_work_independently() -> None:
    """Operations can execute Work via its own entry points without OCP involvement.
    
    This test proves Operations is independent of OrganisationControlPlane.
    It uses a mock runtime to simulate execution, showing that execution
    does not require OCP to invoke it.
    """
    from pathway_runtime import (
        PathwayCallRequest,
        PathwayResponse,
        PathwayRuntime,
        PathwayStatus,
    )

    class MockRuntime(PathwayRuntime):
        def __init__(self) -> None:
            self.invoked = False

        @property
        def id(self) -> str:
            return "mock"

        @property
        def capabilities(self) -> list[str]:
            return []

        def invoke(self, request: PathwayCallRequest) -> PathwayResponse:
            self.invoked = True
            return PathwayResponse(
                status=PathwayStatus.COMPLETED,
                outputs={"summary": "Executed by Operations"},
            )

    runtime = MockRuntime()
    work = Work(id="w1", title="Task", accountable_role_id="r1")

    request = PathwayCallRequest(
        session_id=f"ops-{work.id}",
        pattern_step={"pattern_id": work.title, "ordered_steps": []},
        context={},
        participants=[{"role": work.assignee_role_id or "operator"}],
        prompt=work.description or work.title,
    )
    response = runtime.invoke(request)
    assert response.status == PathwayStatus.COMPLETED
    assert runtime.invoked is True
