"""
Architectural tests for Increment 50 — People/Capability as organisational
capacity/capability function.

Investigation-only increment. No production code is changed or added to satisfy
these tests. The tests assert architectural *contracts* that the existing
domain primitives already satisfy: People/Capability can be understood as an
ordinary organisational function (Role + Actor) that uses the existing capability,
assignment, proficiency, work and organisational-change primitives to reason about
capability/capac ity, not as a conventional HR/staffing domain.

Contracts covered (matching tasks/increment50 requirements):
  1.  People/Capability can be represented as Role + Actor.
  2.  Its Actor can hold capabilities through CapabilityAssignment.
  3.  Its proficiency can be represented through CapabilityProficiency.
  4.  Capability gaps can be identified without an HR entity.
  5.  Capacity can be analysed/derived from Actors + Assignments + Proficiency + Work.
  6.  Capability-exists / Actor-possesses / Actor-assigned / Actor-proficient /
      Actor-has-capacity / aggregate-capacity are individually expressible.
  7.  An existing Actor can be developed to close a gap.
  8.  An existing Actor can be reassigned.
  9.  Additional capacity can be represented through an additional Agent.
  10. Additional capacity can be represented through an additional Person.
  11. Person and Agent use the same Actor boundary.
  12. A new Actor can receive CapabilityAssignment.
  13. Organisational change can use OCP.execute_organisational_change().
  14. Paperclip implementation can use create_work / create_agent / role mapping.
  15. Authority and Delegation remain required for organisational change.
  16. Workflow is a valid response where an existing workflow is appropriate.
  17. Tool is a valid response where a tool capability is appropriate.
  18. HUMAN_TEAM_INVESTIGATION is a valid response.
  19. Outsourcing is explicitly unsupported (no Supplier/Vendor model).
  20. Capability development remains compatible with Increment 48.
  21. Increment 48 identity invariant remains intact (capability_id chain).
  22. required_capability_ids is NOT confused with develops_capability_id.
  23. People/Capability itself can be subject to a capability gap.
  24. A gap in People/Capability can lead to development/provisioning.
  25. No HR/Employee/Workforce/Capacity/Hiring/Staffing/Team/Decision entity
      is required by the model.

Additional locked-down contracts:
  - Chief of Staff remains an ordinary Role (no special executive entity).
  - CapacityPressureSignal exists as a signal, not an entity.
  - No Supplier/Vendor class is introduced anywhere in the organisation,
    people_capability or contracts source trees.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest
from actor import Actor, ActorType
from agent import Agent, AgentMarker, AgentStatus
from agent_store import InMemoryAgentStore
from capability import Capability, CapabilityKind, CapabilityStatus
from capability_assignment import (
    AssignmentStatus as CapAssignmentStatus,
)
from capability_proficiency import CapabilityProficiency, ProficiencyLevel

from execution_path import ExecutionPath
from organisation_control_plane import InMemoryOrganisationControlPlane
from role import (
    Authority,
    Role,
    Work,
    WorkStatus,
)

# --------------------------------------------------------------------------- #
# Shared bootstrap helpers
# --------------------------------------------------------------------------- #

PEOPLE_FUNCTION_ROLE_ID = "people-capability-function"
CHIEF_OF_STAFF_ROLE_ID = "chief-of-staff"
ORG_CHANGE_AUTH_ID = "auth-organisational-change"


def _bootstrap_organisation() -> tuple[InMemoryAgentStore, InMemoryOrganisationControlPlane, Agent, Actor]:
    """Build a minimal organisation where People/Capability is an ordinary Role
    whose Actor is backed by an Agent, and a Chief of Staff Role delegates the
    organisational-change authority to it."""
    store = InMemoryAgentStore()
    ocp = InMemoryOrganisationControlPlane()

    chief = Role(
        id=CHIEF_OF_STAFF_ROLE_ID,
        name="Chief of Staff",
        authority_ids=[],
        reports_to=None,
    )
    ocp.register_role(chief)

    pc_role = Role(
        id=PEOPLE_FUNCTION_ROLE_ID,
        name="People / Capability Function",
        description="Organisational capacity/capability function",
        authority_ids=[ORG_CHANGE_AUTH_ID],
        reports_to=CHIEF_OF_STAFF_ROLE_ID,
        required_capability_ids=["cap-analyse-capacity"],
    )
    ocp.register_role(pc_role)

    auth = Authority(
        id=ORG_CHANGE_AUTH_ID,
        name="Organisational change authority",
        scope="organisation",
        grantor_role_id=CHIEF_OF_STAFF_ROLE_ID,
        grantee_role_id=PEOPLE_FUNCTION_ROLE_ID,
    )
    ocp.register_authority(auth)
    ocp.delegate_authority(chief, pc_role, auth)

    # People/Capability function is realised by an Agent (software executor).
    pc_agent = Agent(
        id="agent-people-capability",
        name="People Capability Assistant",
        marker=AgentMarker.AI,
        status=AgentStatus.ACTIVE,
        fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
    )
    store.register_agent(pc_agent)
    pc_actor = store.get_actor(pc_agent.id)
    assert pc_actor is not None
    assert pc_actor.actor_type == ActorType.AGENT

    return store, ocp, pc_agent, pc_actor


def _make_work(
    work_id: str = "w-test",
    develops_capability_id: str | None = None,
    required_capability_ids: list[str] | None = None,
    work_type: str = "bau",
) -> Work:
    return Work(
        id=work_id,
        title="Test work",
        description="unit of organisational effort",
        work_type=work_type,
        accountable_role_id=PEOPLE_FUNCTION_ROLE_ID,
        required_capability_ids=required_capability_ids or [],
        develops_capability_id=develops_capability_id,
        status=WorkStatus.PENDING,
    )


def _derive_available_capacity(
    store: InMemoryAgentStore,
    required_capability_ids: list[str],
    in_progress_work_count: dict[str, int] | None = None,
) -> dict[str, int]:
    """Analytical capacity derivation — NOT an entity.

    available actor slots for a capability =
        (actors assigned that capability, ACTIVE proficiency assumed)
        minus (actors already saturated by in-progress work on that capability)

    This function exists only to prove the *inputs* are representable and
    combinable; it is the seed of a future capacity-analysis service, not a
    People/Capability domain entity.
    """
    in_progress_work_count = in_progress_work_count or {}
    available: dict[str, int] = {}
    for cap_id in required_capability_ids:
        assignments = store.get_assignments_for_capability(cap_id)
        actor_count = len({a.actor_id for a in assignments})
        saturated = in_progress_work_count.get(cap_id, 0)
        available[cap_id] = max(0, actor_count - saturated)
    return available


# --------------------------------------------------------------------------- #
# 1. People/Capability can be represented as Role + Actor.
# --------------------------------------------------------------------------- #


class TestPeopleCapabilityAsRoleAndActor:
    """People/Capability is an ordinary Role whose execution identity is an
    Actor (ActorType.AGENT here). No special executive entity is required."""

    def test_people_capability_is_a_role(self) -> None:
        _, ocp, _, _ = _bootstrap_organisation()
        role = ocp.get_role(PEOPLE_FUNCTION_ROLE_ID)
        assert role is not None
        assert role.name == "People / Capability Function"
        assert role.reports_to == CHIEF_OF_STAFF_ROLE_ID

    def test_people_capability_has_an_actor_identity(self) -> None:
        store, _, _, actor = _bootstrap_organisation()
        assert actor.id == "agent-people-capability"
        assert actor.actor_type == ActorType.AGENT
        assert store.get_actor(actor.id) is not None

    def test_chief_of_staff_is_an_ordinary_role(self) -> None:
        """Chief of Staff is a Role, not an executive/CEO entity."""
        _, ocp, _, _ = _bootstrap_organisation()
        role = ocp.get_role(CHIEF_OF_STAFF_ROLE_ID)
        assert role is not None
        assert role.id == "chief-of-staff"
        # Authority is granted/delegated through the same primitives.
        assert ocp.get_role(PEOPLE_FUNCTION_ROLE_ID).authority_ids == [ORG_CHANGE_AUTH_ID]


# --------------------------------------------------------------------------- #
# 2. Its Actor can hold capabilities through CapabilityAssignment.
# --------------------------------------------------------------------------- #


class TestCapabilityAssignmentForPeopleCapability:
    def test_actor_holds_capability_through_assignment(self) -> None:
        store, _, _, actor = _bootstrap_organisation()
        assignment = store.assign_capability(actor.id, "cap-analyse-capacity")
        assert assignment.actor_id == actor.id
        assert assignment.capability_id == "cap-analyse-capacity"
        assert assignment.status == CapAssignmentStatus.ACTIVE
        assert store.actor_has_capability(actor.id, "cap-analyse-capacity") is True


# --------------------------------------------------------------------------- #
# 3. Its proficiency can be represented through CapabilityProficiency.
# --------------------------------------------------------------------------- #


class TestCapabilityProficiencyRepresentation:
    def test_proficiency_record_links_actor_and_capability(self) -> None:
        _, _, _, actor = _bootstrap_organisation()
        proficiency = CapabilityProficiency(
            id="prof-1",
            capability_id="cap-analyse-capacity",
            actor_id=actor.id,
            proficiency_level=ProficiencyLevel.PROFICIENT,
        )
        assert proficiency.actor_id == actor.id
        assert proficiency.capability_id == "cap-analyse-capacity"
        assert proficiency.proficiency_level == ProficiencyLevel.PROFICIENT


# --------------------------------------------------------------------------- #
# 4. Capability gaps can be identified without an HR entity.
# --------------------------------------------------------------------------- #


class TestCapabilityGapIdentification:
    def test_missing_capability_is_a_gap_without_hr_entity(self) -> None:
        _, ocp, _, _ = _bootstrap_organisation()
        # No capability "cap-never-heard-of" is registered anywhere.
        result = ocp.select_execution_path(
            intent="do something nobody can do",
            context={"required_capability_ids": ["cap-never-heard-of"]},
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id == "cap-never-heard-of"

    def test_existing_capability_is_not_a_gap(self) -> None:
        store, ocp, _, actor = _bootstrap_organisation()
        store.assign_capability(actor.id, "cap-analyse-capacity")
        ocp.register_capability(
            Capability(
                id="cap-analyse-capacity",
                name="analyse capacity",
                capability_kind=CapabilityKind.SKILL,
                status=CapabilityStatus.ACTIVE,
            )
        )
        result = ocp.select_execution_path(
            intent="analyse capacity",
            context={"required_capability_ids": ["cap-analyse-capacity"]},
        )
        assert result.path == ExecutionPath.CAPABILITY_PATH
        assert result.capability_id == "cap-analyse-capacity"


# --------------------------------------------------------------------------- #
# 5. Capacity can be analysed/derived from existing Actors, Assignments,
#    Proficiency, Work and availability information.
# --------------------------------------------------------------------------- #


class TestCapacityAnalysisDerivation:
    def test_capacity_is_derived_from_existing_state_not_an_entity(self) -> None:
        """There is no Capacity entity; capacity is a derived analytical result."""
        store, _, _, _ = _bootstrap_organisation()

        agent = Agent(
            id="agent-c1",
            name="Analyst",
            marker=AgentMarker.AI,
            status=AgentStatus.ACTIVE,
            fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        store.register_agent(agent)
        actor = store.get_actor(agent.id)
        store.assign_capability(actor.id, "cap-analyse-capacity")
        store.assign_capability(actor.id, "cap-assess-proficiency")

        in_progress = {"cap-analyse-capacity": 1}
        available = _derive_available_capacity(
            store,
            ["cap-analyse-capacity", "cap-assess-proficiency"],
            in_progress_work_count=in_progress,
        )
        assert available["cap-assess-proficiency"] == 1  # fully available
        assert available["cap-analyse-capacity"] == 0  # saturated

    def test_capacity_pressure_signal_is_a_signal_not_an_entity(self) -> None:
        from contracts.organisational_events import CapacityPressureSignal

        _, ocp, _, _ = _bootstrap_organisation()
        role = ocp.get_role(PEOPLE_FUNCTION_ROLE_ID)
        assert role is not None
        work = _make_work(work_id="w-load-1", required_capability_ids=["cap-analyse-capacity"])
        ocp.assign_work(work, Role(id=PEOPLE_FUNCTION_ROLE_ID, name="People"))

        pressure = ocp.detect_capacity_pressure("cap-analyse-capacity")
        # Single in-progress item => no pressure signal (load not > 1), but the
        # method exists and is purely analytical.
        assert pressure is None

        work2 = _make_work(work_id="w-load-2", required_capability_ids=["cap-analyse-capacity"])
        ocp.assign_work(work2, Role(id=PEOPLE_FUNCTION_ROLE_ID, name="People"))
        pressure = ocp.detect_capacity_pressure("cap-analyse-capacity")
        assert isinstance(pressure, CapacityPressureSignal)
        assert pressure.capability_id == "cap-analyse-capacity"


# --------------------------------------------------------------------------- #
# 6. The model distinguishes the six representation layers.
# --------------------------------------------------------------------------- #


class TestSixLayerDistinction:
    def test_capability_exists_in_registry(self) -> None:
        _, ocp, _, _ = _bootstrap_organisation()
        ocp.register_capability(
            Capability(
                id="cap-exists-1",
                name="exists",
                capability_kind=CapabilityKind.SKILL,
                status=CapabilityStatus.ACTIVE,
            )
        )
        assert ocp.get_capability("cap-exists-1") is not None
        assert ocp.get_capability("cap-missing-1") is None

    def test_actor_possesses_capability(self) -> None:
        store, _, _, actor = _bootstrap_organisation()
        store.assign_capability(actor.id, "cap-possessed-1")
        assert store.actor_has_capability(actor.id, "cap-possessed-1") is True

    def test_actor_is_assigned_capability(self) -> None:
        store, _, _, actor = _bootstrap_organisation()
        assignment = store.assign_capability(actor.id, "cap-assigned-1")
        assignments = store.get_assignments_for_actor(actor.id)
        assert any(a.capability_id == "cap-assigned-1" for a in assignments)
        assert assignment.status == CapAssignmentStatus.ACTIVE

    def test_actor_is_sufficiently_proficient(self) -> None:
        _, _, _, actor = _bootstrap_organisation()
        proficiency = CapabilityProficiency(
            id="prof-2",
            capability_id="cap-proficient-1",
            actor_id=actor.id,
            proficiency_level=ProficiencyLevel.EXPERT,
        )
        assert proficiency.proficiency_level is ProficiencyLevel.EXPERT

    def test_actor_has_capacity(self) -> None:
        available = _derive_available_capacity(
            InMemoryAgentStore(), ["cap-x"], in_progress_work_count={}
        )
        # No actors assigned => zero capacity; the *computation* is representable.
        assert available["cap-x"] == 0

    def test_organisation_has_aggregate_capacity(self) -> None:
        store, _, _, _ = _bootstrap_organisation()
        for name in ("agent-g1", "agent-g2"):
            agent = Agent(
                id=name,
                name=name,
                marker=AgentMarker.AI,
                status=AgentStatus.ACTIVE,
                fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
            )
            store.register_agent(agent)
            actor = store.get_actor(agent.id)
            assert actor is not None
            store.assign_capability(actor.id, "cap-aggregate-1")
        available = _derive_available_capacity(store, ["cap-aggregate-1"])
        assert available["cap-aggregate-1"] == 2


# --------------------------------------------------------------------------- #
# 7. An existing Actor can be developed to close a gap (Increment 48 path).
# --------------------------------------------------------------------------- #


class TestDevelopingExistingActor:
    def test_existing_actor_development_through_increment48_lifecycle(self, tmp_path) -> None:
        from workflow_runner.src.worker import Worker

        from outcome import assess_capability_development

        _, ocp, _, actor = _bootstrap_organisation()

        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore

        concept_store = ConceptStore(data_dir=str(tmp_path / "concepts"))
        repo = ConceptStoreCapabilityRepository(concept_store)
        registry = CapabilityRegistry(repo)
        ocp._capability_registry = registry

        capability_id = "cap-developed-by-actor"
        ocp.register_role(Role(id="default", name="Default"))

        path_result = ocp.select_execution_path(
            intent="need a capability an actor can develop",
            context={"required_capability_ids": [capability_id]},
        )
        assert path_result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert path_result.capability_id == capability_id

        work = Work(
            id="w-develop-actor",
            title="Develop capability: By Actor",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=path_result.capability_id,
            status=WorkStatus.READY,
            assignee_actor_id=actor.id,
        )

        worker = Worker(
            output_dir=str(tmp_path / "worker_out_develop"),
            capability_registry=registry,
        )
        result = worker._develop_capability(work, ocp)
        assert result["capability_id"] == capability_id

        developed = registry.get(capability_id)
        assert developed is not None
        assert developed.id == capability_id
        assert developed.status == CapabilityStatus.DRAFT

        assessment = assess_capability_development(work, developed, result)
        assert assessment["passed"] is True
        registry.promote(capability_id)
        assert registry.get(capability_id).status == CapabilityStatus.ACTIVE


# --------------------------------------------------------------------------- #
# 8. An existing Actor can be reassigned.
# --------------------------------------------------------------------------- #


class TestActorReassignment:
    def test_actor_reassigned_via_assignment_status(self) -> None:
        store, _, _, actor = _bootstrap_organisation()
        old = store.assign_capability(actor.id, "cap-old-1")
        new = store.assign_capability(actor.id, "cap-new-1")

        # Reassignment: suspend the old, keep the new active.
        old.status = CapAssignmentStatus.SUSPENDED
        active = store.get_assignments_for_actor(actor.id)
        assert all(a.status == CapAssignmentStatus.ACTIVE for a in active)
        assert "cap-new-1" in [a.capability_id for a in active]
        assert "cap-old-1" not in [a.capability_id for a in active]
        assert new.status == CapAssignmentStatus.ACTIVE


# --------------------------------------------------------------------------- #
# 9. Additional capacity can be represented through an additional Agent.
# --------------------------------------------------------------------------- #


class TestNewAgentProvision:
    def test_additional_agent_provisions_capacity(self) -> None:
        store, _, _, _ = _bootstrap_organisation()
        agent = Agent(
            id="agent-extra-1",
            name="Extra Agent",
            marker=AgentMarker.AI,
            status=AgentStatus.ACTIVE,
            fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        store.register_agent(agent)
        actor = store.get_actor(agent.id)
        assert actor is not None
        assert actor.actor_type == ActorType.AGENT
        store.assign_capability(actor.id, "cap-analyse-capacity")
        assert store.actor_has_capability(actor.id, "cap-analyse-capacity") is True


# --------------------------------------------------------------------------- #
# 10. Additional capacity can be represented through an additional Person.
# --------------------------------------------------------------------------- #


class TestNewPersonProvision:
    def test_additional_person_provisions_capacity(self) -> None:
        store, _, _, _ = _bootstrap_organisation()
        from person import Person, PersonStatus

        person = Person(
            id="person-extra-1",
            name="Extra Person",
            status=PersonStatus.ACTIVE,
            role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        store.register_person(person)
        actor = store.get_actor(person.id)
        assert actor is not None
        assert actor.actor_type == ActorType.PERSON
        store.assign_capability(actor.id, "cap-assess-proficiency")
        assert store.actor_has_capability(actor.id, "cap-assess-proficiency") is True


# --------------------------------------------------------------------------- #
# 11. Person and Agent use the same Actor boundary.
# --------------------------------------------------------------------------- #


class TestPersonAgentActorBoundary:
    def test_person_and_agent_both_produce_actor_identities(self) -> None:
        store, _, _, _ = _bootstrap_organisation()
        from person import Person, PersonStatus

        agent = Agent(
            id="agent-symmetry",
            name="Agent",
            marker=AgentMarker.AI,
            status=AgentStatus.ACTIVE,
            fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        person = Person(
            id="person-symmetry",
            name="Person",
            status=PersonStatus.ACTIVE,
            role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        store.register_agent(agent)
        store.register_person(person)

        agent_actor = store.get_actor(agent.id)
        person_actor = store.get_actor(person.id)
        assert agent_actor is not None and person_actor is not None
        assert isinstance(agent_actor, Actor)
        assert isinstance(person_actor, Actor)
        assert agent_actor.actor_type == ActorType.AGENT
        assert person_actor.actor_type == ActorType.PERSON

    def test_same_assignment_mechanism_for_both(self) -> None:
        store, _, _, _ = _bootstrap_organisation()
        from person import Person, PersonStatus

        agent = Agent(
            id="agent-sym-a",
            name="Agent A",
            marker=AgentMarker.AI,
            status=AgentStatus.ACTIVE,
            fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        person = Person(
            id="person-sym-p",
            name="Person P",
            status=PersonStatus.ACTIVE,
            role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        store.register_agent(agent)
        store.register_person(person)

        agent_actor = store.get_actor(agent.id)
        person_actor = store.get_actor(person.id)
        store.assign_capability(agent_actor.id, "cap-shared")
        store.assign_capability(person_actor.id, "cap-shared")

        assert store.actor_has_capability(agent_actor.id, "cap-shared") is True
        assert store.actor_has_capability(person_actor.id, "cap-shared") is True


# --------------------------------------------------------------------------- #
# 12. A new Actor can receive a CapabilityAssignment.
# --------------------------------------------------------------------------- #


class TestNewActorAssignment:
    def test_newly_provisioned_actor_receives_assignment(self) -> None:
        store, _, _, _ = _bootstrap_organisation()
        agent = Agent(
            id="agent-new",
            name="New",
            marker=AgentMarker.AI,
            status=AgentStatus.ACTIVE,
            fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        store.register_agent(agent)
        actor = store.get_actor(agent.id)
        assignment = store.assign_capability(actor.id, "cap-fresh-1")
        assert assignment.actor_id == actor.id
        assert store.get_assignments_for_actor(actor.id)[0].capability_id == "cap-fresh-1"


# --------------------------------------------------------------------------- #
# 13. Organisational change can use OCP.execute_organisational_change().
# --------------------------------------------------------------------------- #


class TestExecuteOrganisationalChange:
    def test_execute_organisational_change_succeeds_with_delegated_authority(self) -> None:
        _, ocp, _, actor = _bootstrap_organisation()
        work = _make_work(work_id="w-change-1", required_capability_ids=["cap-changed-1"])
        result = ocp.execute_organisational_change(work, actor, capability_ids=["cap-changed-1"])
        assert result["status"] == "executed"
        assert result["authority_checked"] is True
        assert result["assignee_actor_id"] == actor.id
        assert ocp.get_work("w-change-1") is not None

    def test_execute_organisational_change_is_idempotent(self) -> None:
        _, ocp, _, actor = _bootstrap_organisation()
        work = _make_work(work_id="w-change-2", required_capability_ids=["cap-changed-2"])
        first = ocp.execute_organisational_change(work, actor, capability_ids=["cap-changed-2"])
        assert first["status"] == "executed"
        second = ocp.execute_organisational_change(work, actor, capability_ids=["cap-changed-2"])
        assert second["status"] == "idempotent"


# --------------------------------------------------------------------------- #
# 14. Paperclip implementation can use create_work / create_agent / role mapping.
# --------------------------------------------------------------------------- #


class TestPaperclipMechanisms:
    def test_paperclip_exposes_create_work_and_create_agent(self) -> None:
        pytest.importorskip("httpx")
        from organisation_paperclip import PaperclipOrganisationControlPlane

        plane = PaperclipOrganisationControlPlane(base_url="http://127.0.0.1:3999")
        sig_work = inspect.signature(plane.create_work)
        sig_agent = inspect.signature(plane.create_agent)
        assert "title" in sig_work.parameters
        assert "required_capability_ids" in sig_work.parameters
        assert "name" in sig_agent.parameters
        assert "capabilities" in sig_agent.parameters

    def test_paperclip_maps_agent_json_to_role_with_capabilities(self) -> None:
        pytest.importorskip("httpx")
        from organisation_paperclip import PaperclipOrganisationControlPlane

        plane = PaperclipOrganisationControlPlane(base_url="http://127.0.0.1:3999")
        mapped = plane._map_agent_to_role(
            {
                "id": "pc-agent-1",
                "name": "Paperclip Agent",
                "title": "A Role Title",
                "status": "active",
                "capabilities": "cap-a, cap-b",
                "reportsTo": "chief-of-staff",
                "metadata": {},
            }
        )
        assert mapped.id == "pc-agent-1"
        assert mapped.required_capability_ids == ["cap-a", "cap-b"]
        assert mapped.reports_to == "chief-of-staff"


# --------------------------------------------------------------------------- #
# 15. Authority and Delegation remain required for organisational change.
# --------------------------------------------------------------------------- #


class TestAuthorityAndDelegationRequired:
    def test_unauthorised_role_blocks_change(self) -> None:
        _, ocp, _, actor = _bootstrap_organisation()
        role_no_auth = Role(
            id="role-no-auth",
            name="No Authority",
            authority_ids=[ORG_CHANGE_AUTH_ID],  # listed but never delegated
        )
        ocp.register_role(role_no_auth)
        work = Work(
            id="w-unauth",
            title="Unauthorised change",
            accountable_role_id="role-no-auth",
            required_capability_ids=["cap-x"],
        )
        result = ocp.execute_organisational_change(work, actor)
        assert result["status"] == "unauthorised"
        assert result["authority_checked"] is True

    def test_delegated_authority_permits_change(self) -> None:
        _, ocp, _, actor = _bootstrap_organisation()
        work = _make_work(
            work_id="w-auth",
            required_capability_ids=["cap-y"],
        )
        result = ocp.execute_organisational_change(work, actor)
        assert result["status"] == "executed"

    def test_delegation_record_is_required_not_just_authority_id(self) -> None:
        _, ocp, _, _ = _bootstrap_organisation()
        auth = ocp._authorities.get(ORG_CHANGE_AUTH_ID)
        assert auth is not None
        assert ocp.get_role(PEOPLE_FUNCTION_ROLE_ID) is not None
        # A delegation was minted by _bootstrap_organisation.
        assert any(
            d.authority_id == ORG_CHANGE_AUTH_ID
            and d.to_role_id == PEOPLE_FUNCTION_ROLE_ID
            for d in ocp._delegations.values()
        )


# --------------------------------------------------------------------------- #
# 16. Workflow is a valid response where an existing workflow is appropriate.
# --------------------------------------------------------------------------- #


class TestExistingWorkflowResponse:
    def test_existing_workflow_selected_when_lookup_returns_definition(self) -> None:
        _, ocp, _, _ = _bootstrap_organisation()
        workflow_def = {"id": "wf-capacity", "name": "capacity workflow"}

        def lookup(intent: str) -> list[Any]:
            if "capacity" in intent:
                return [workflow_def]
            return []

        result = ocp.select_execution_path(
            intent="analyse capacity",
            context={"required_capability_ids": ["cap-analyse-capacity"]},
            workflow_lookup=lookup,
        )
        assert result.path == ExecutionPath.EXISTING_WORKFLOW
        assert result.workflow == workflow_def


# --------------------------------------------------------------------------- #
# 17. Tool is a valid response where a tool capability is appropriate.
# --------------------------------------------------------------------------- #


class TestToolResponse:
    def test_tool_capability_kind_is_representable(self) -> None:
        assert CapabilityKind.TOOL is CapabilityKind.TOOL
        assert CapabilityKind.TOOL != CapabilityKind.SKILL

    def test_tool_capability_can_be_assigned(self) -> None:
        store, _, _, actor = _bootstrap_organisation()
        tool = Capability(
            id="cap-tool-1",
            name="tool",
            capability_kind=CapabilityKind.TOOL,
            status=CapabilityStatus.ACTIVE,
            standing_contract=True,
            owns_durable_state=True,
        )
        assert tool.capability_kind == CapabilityKind.TOOL
        store.assign_capability(actor.id, "cap-tool-1")
        assert store.actor_has_capability(actor.id, "cap-tool-1") is True


# --------------------------------------------------------------------------- #
# 18. HUMAN_TEAM_INVESTIGATION is a valid response.
# --------------------------------------------------------------------------- #


class TestHumanTeamInvestigationResponse:
    def test_human_investigation_when_capability_exists_but_unavailable(self) -> None:
        _, ocp, _, _ = _bootstrap_organisation()

        def query(capability_id: str) -> Any:
            class _Avail:
                available = False
                reason = "In use / needs human review"
                assignee = None
            return _Avail()

        result = ocp.select_execution_path(
            intent="investigate ambiguous need",
            context={"required_capability_ids": ["cap-ambiguous"]},
            capability_query=query,
        )
        assert result.path == ExecutionPath.HUMAN_TEAM_INVESTIGATION
        assert result.capability_id == "cap-ambiguous"


# --------------------------------------------------------------------------- #
# 19. Outsourcing is explicitly unsupported (no Supplier/Vendor model).
# --------------------------------------------------------------------------- #

_FORBIDDEN_CLASSES = {"Supplier", "Vendor", "Employee", "Workforce", "Capacity",
                       "Hiring", "Recruitment", "Staffing", "Team", "Decision",
                       "SelfImprovement", "HR", "CapabilityDefinition"}


def _scan_src_for_classes(packages: list[str]) -> set[str]:
    found: set[str] = set()
    root = Path(__file__).resolve().parents[3]  # packages/
    import re

    pattern = r"class (\w+)\b"
    for pkg in packages:
        pkg_src = root / pkg / "src"
        if not pkg_src.exists():
            continue
        for path in pkg_src.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(pattern, text):
                name = match.group(1)
                if name in _FORBIDDEN_CLASSES:
                    found.add(name)
    return found


class TestOutsourcingUnsupported:
    def test_no_supplier_or_vendor_class_exists(self) -> None:
        found = _scan_src_for_classes(["organisation", "people_capability", "contracts"])
        assert "Supplier" not in found
        assert "Vendor" not in found

    def test_execution_path_has_no_outsource_member(self) -> None:
        assert not hasattr(ExecutionPath, "OUTSOURCE")
        assert "outsource" not in [p.value for p in ExecutionPath]


# --------------------------------------------------------------------------- #
# 20. Capability development remains compatible with Increment 48.
# --------------------------------------------------------------------------- #


class TestIncrement48Compatibility:
    def test_increment48_chain_remains_intact(self, tmp_path) -> None:
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore
        from workflow_runner.src.worker import Worker

        from outcome import assess_capability_development

        _, ocp, _, _ = _bootstrap_organisation()

        concept_store = ConceptStore(data_dir=str(tmp_path / "concepts48"))
        repo = ConceptStoreCapabilityRepository(concept_store)
        registry = CapabilityRegistry(repo)
        ocp._capability_registry = registry
        ocp.register_role(Role(id="default", name="Default"))

        original_id = "cap-chain-48-i50"
        path_result = ocp.select_execution_path(
            intent="missing cap",
            context={"required_capability_ids": [original_id]},
        )
        assert path_result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert path_result.capability_id == original_id

        work = Work(
            id="w-chain-48-i50",
            title="Develop capability: Chain",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=path_result.capability_id,
            status=WorkStatus.READY,
        )
        worker = Worker(
            output_dir=str(tmp_path / "worker_out_48"),
            capability_registry=registry,
        )
        result = worker._develop_capability(work, ocp)
        assert result["capability_id"] == original_id

        cap = registry.get(original_id)
        assert cap.id == original_id
        assert cap.status == CapabilityStatus.DRAFT

        assessment = assess_capability_development(work, cap, result)
        assert assessment["passed"] is True
        promoted = registry.promote(original_id)
        assert promoted.status == CapabilityStatus.ACTIVE
        assert promoted.id == original_id


# --------------------------------------------------------------------------- #
# 21. Increment 48 identity invariant remains intact.
# --------------------------------------------------------------------------- #


class TestIncrement48IdentityInvariant:
    """ExecutionPathResult.capability_id
        -> Work.develops_capability_id
        -> Capability.id
        -> CapabilityRegistry.get
        -> assessment
        -> ACTIVE
    """

    def test_identity_survives_every_hop(self, tmp_path) -> None:
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore
        from workflow_runner.src.worker import Worker

        from outcome import assess_capability_development

        _, ocp, _, _ = _bootstrap_organisation()
        concept_store = ConceptStore(data_dir=str(tmp_path / "concepts_inv"))
        registry = CapabilityRegistry(ConceptStoreCapabilityRepository(concept_store))
        ocp._capability_registry = registry
        ocp.register_role(Role(id="default", name="Default"))

        capability_id = "cap-invariant-50"

        path_result = ocp.select_execution_path(
            intent="invariant check",
            context={"required_capability_ids": [capability_id]},
        )
        # Hop 1: capability_id is preserved on NEW_CAPABILITY_REQUIRED.
        assert path_result.capability_id == capability_id

        work = Work(
            id="w-invariant-50",
            title="Develop capability: Invariant",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=path_result.capability_id,  # Hop 2
        )
        assert work.develops_capability_id == capability_id

        worker = Worker(
            output_dir=str(tmp_path / "worker_out_inv"),
            capability_registry=registry,
        )
        result = worker._develop_capability(work, ocp)
        # Hop 3 + 4: Worker uses develops_capability_id; registry now holds it.
        assert result["capability_id"] == capability_id
        cap = registry.get(capability_id)
        assert cap.id == capability_id  # Hop 4: identity survives registration
        assert cap.status == CapabilityStatus.DRAFT

        assessment = assess_capability_development(work, cap, result)  # Hop: assessment
        assert assessment["passed"] is True
        registry.promote(capability_id)  # Hop -> assessment -> ACTIVE
        assert registry.get(capability_id).status == CapabilityStatus.ACTIVE


# --------------------------------------------------------------------------- #
# 22. required_capability_ids is NOT confused with develops_capability_id.
# --------------------------------------------------------------------------- #


class TestSemanticSeparationOfCapabilityFields:
    def test_required_and_develops_are_independent(self) -> None:
        work = Work(
            id="w-sep-1",
            title="Develop capability: Separation",
            work_type="capability_development",
            accountable_role_id=PEOPLE_FUNCTION_ROLE_ID,
            required_capability_ids=["cap-required-to-execute"],
            develops_capability_id="cap-being-developed",
        )
        assert "cap-being-developed" not in work.required_capability_ids
        assert work.develops_capability_id == "cap-being-developed"
        assert work.required_capability_ids == ["cap-required-to-execute"]

    def test_bau_work_has_no_develops_field(self) -> None:
        work = Work(
            id="w-bau",
            title="Routine work",
            work_type="bau",
            accountable_role_id=PEOPLE_FUNCTION_ROLE_ID,
        )
        assert work.develops_capability_id is None


# --------------------------------------------------------------------------- #
# 23. People/Capability itself can be subject to a capability gap.
# --------------------------------------------------------------------------- #


class TestPeopleCapabilitySubjectToGap:
    def test_people_capability_capability_can_be_missing(self) -> None:
        _, ocp, _, _ = _bootstrap_organisation()
        pc_capability = "cap-people-capability-analyse"
        result = ocp.select_execution_path(
            intent="people/capability function needs its own capability",
            context={"required_capability_ids": [pc_capability]},
        )
        # The function is modelled as an Actor holding capabilities; if its own
        # capability is missing, the same gap-detection machinery applies.
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id == pc_capability

    def test_people_capability_can_hold_proficiency(self) -> None:
        store, _, _, actor = _bootstrap_organisation()
        store.assign_capability(actor.id, "cap-analyse-capacity")
        proficiency = CapabilityProficiency(
            id="prof-pc",
            capability_id="cap-analyse-capacity",
            actor_id=actor.id,
            proficiency_level=ProficiencyLevel.PROFICIENT,
        )
        assert proficiency.actor_id == actor.id


# --------------------------------------------------------------------------- #
# 24. A gap in People/Capability can lead to development/provisioning.
# --------------------------------------------------------------------------- #


class TestPeopleCapabilitySelfImprovementPath:
    """People/Capability is an Actor, so the same loop applies recursively:
    gap -> development or provisioning -> assignment -> work -> evidence ->
    reassessment. No SelfImprovement or HR entity is introduced."""

    def test_gap_leads_to_developable_work(self) -> None:
        _, ocp, _, actor = _bootstrap_organisation()
        gap_id = "cap-self-develop-1"
        path = ocp.select_execution_path(
            intent="people/capability needs to develop a capability",
            context={"required_capability_ids": [gap_id]},
        )
        assert path.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert path.capability_id == gap_id

        work = Work(
            id="w-self-develop",
            title=f"Develop capability: {gap_id}",
            work_type="capability_development",
            accountable_role_id=PEOPLE_FUNCTION_ROLE_ID,
            develops_capability_id=path.capability_id,
        )
        assert work.develops_capability_id == gap_id
        # The work is assignable to the People/Capability Actor (recursive).
        ocp.assign_work(work, actor)
        assert work.assignee_actor_id == actor.id

    def test_gap_leads_to_provisionable_actor(self) -> None:
        store, _, _, _ = _bootstrap_organisation()
        new_agent = Agent(
            id="agent-provisioned",
            name="Provisioned",
            marker=AgentMarker.AI,
            status=AgentStatus.ACTIVE,
            fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        store.register_agent(new_agent)
        new_actor = store.get_actor(new_agent.id)
        assert new_actor is not None
        store.assign_capability(new_actor.id, "cap-self-develop-1")
        assert store.actor_has_capability(new_actor.id, "cap-self-develop-1") is True


# --------------------------------------------------------------------------- #
# 25. No HR/Employee/Workforce/Capacity/Hiring/Staffing/Team/Decision entity.
# --------------------------------------------------------------------------- #


class TestNoHrStaffingEntities:
    def test_no_forbidden_entities_in_organisation_src(self) -> None:
        found = _scan_src_for_classes(["organisation"])
        assert found == set(), f"Forbidden entities found: {found}"

    def test_no_forbidden_entities_in_people_capability_src(self) -> None:
        found = _scan_src_for_classes(["people_capability"])
        assert found == set(), f"Forbidden entities found: {found}"

    def test_no_forbidden_entities_in_contracts(self) -> None:
        found = _scan_src_for_classes(["contracts"])
        assert found == set(), f"Forbidden entities found: {found}"
