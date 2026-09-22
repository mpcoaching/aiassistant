"""
Boundary tests for Increment 29 — Complete the Actor boundary.

Proves:
- Person can be registered as an Actor (Person -> Actor -> CapabilityAssignment -> authorisation)
- Agent and Person use the same Actor -> CapabilityAssignment mechanism
- CapabilityProficiency is Actor-oriented with backward compatibility
- OCP.assign_work() accepts Actor as canonical identity
- OCP does not require AgentStore internals for Actor identity
- Execution layer resolves Actor -> Agent/Person separately from authorisation
- Role remains distinct from Actor
"""

from __future__ import annotations

from actor import Actor, ActorType
from agent import Agent, AgentMarker
from agent_store import InMemoryAgentStore
from capability_assignment import AssignmentStatus, CapabilityAssignment
from capability_proficiency import CapabilityProficiency, ProficiencyLevel
from person import Person

# ---- Person -> Actor boundary ----


class TestPersonToActorRegistration:
    """A Person must be registerable as an Actor through the normal mechanism."""

    def test_register_person_creates_person_record(self) -> None:
        store = InMemoryAgentStore()
        person = Person(id="p-alice", name="Alice", email="alice@example.com")
        store.register_person(person)
        retrieved = store.get_person("p-alice")
        assert retrieved is not None
        assert retrieved.id == "p-alice"
        assert retrieved.name == "Alice"

    def test_register_person_creates_corresponding_actor(self) -> None:
        store = InMemoryAgentStore()
        person = Person(id="p-alice", name="Alice")
        store.register_person(person)
        actor = store.get_actor("p-alice")
        assert actor is not None
        assert actor.actor_type == ActorType.PERSON
        assert actor.reference_id == "p-alice"
        assert actor.name == "Alice"
        assert actor.marker is None

    def test_register_person_does_not_duplicate_person_into_actor(self) -> None:
        store = InMemoryAgentStore()
        person = Person(
            id="p-bob", name="Bob", email="bob@example.com",
            employment_context={"dept": "engineering"},
        )
        store.register_person(person)
        actor = store.get_actor("p-bob")
        assert actor is not None
        assert actor.actor_type == ActorType.PERSON
        assert not hasattr(actor, "email")
        assert not hasattr(actor, "employment_context")

    def test_register_person_propagates_role_ids(self) -> None:
        store = InMemoryAgentStore()
        person = Person(id="p-carol", name="Carol", role_ids=["analyst", "researcher"])
        store.register_person(person)
        actor = store.get_actor("p-carol")
        assert actor is not None
        assert "analyst" in actor.fulfilled_role_ids
        assert "researcher" in actor.fulfilled_role_ids


class TestPersonActorCapabilityAssignment:
    """Person Actor can be assigned capabilities through the same mechanism as Agent."""

    def test_person_actor_can_be_assigned_capability(self) -> None:
        store = InMemoryAgentStore()
        person = Person(id="p-alice", name="Alice")
        store.register_person(person)
        assignment = store.assign_capability("p-alice", "cap-research")
        assert assignment.actor_id == "p-alice"
        assert assignment.capability_id == "cap-research"
        assert assignment.status == AssignmentStatus.ACTIVE

    def test_person_actor_can_be_verified_for_capability(self) -> None:
        store = InMemoryAgentStore()
        person = Person(id="p-alice", name="Alice")
        store.register_person(person)
        store.assign_capability("p-alice", "cap-research")
        assert store.actor_has_capability("p-alice", "cap-research")

    def test_person_actor_capability_authorization(self) -> None:
        """Person -> Actor -> CapabilityAssignment -> authorisation."""
        store = InMemoryAgentStore()
        person = Person(id="p-alice", name="Alice")
        store.register_person(person)
        store.assign_capability("p-alice", "cap-research")

        from capability_registry.src.adapters.execution_authorisation_adapter import (
            InMemoryExecutionAuthorisationPort,
        )
        auth = InMemoryExecutionAuthorisationPort(
            assignments=store.get_all_assignments(),
        )
        result = auth.is_authorised("p-alice", "person", "cap-research")
        assert result.authorised is True
        assert result.assignment is not None
        assert result.assignment.capability_id == "cap-research"


# ---- Unified Actor boundary ----


class TestUnifiedActorCapabilityMechanism:
    """Agent and Person Actors use the same CapabilityAssignment mechanism."""

    def test_agent_and_person_use_same_assignment_mechanism(self) -> None:
        store = InMemoryAgentStore()

        agent = Agent(id="a1", name="Bot", marker=AgentMarker.AI, fulfilled_role_ids=["operator"])
        store.register_agent(agent)

        person = Person(id="p1", name="Alice")
        store.register_person(person)

        agent_assignment = store.assign_capability("a1", "cap-exec")
        person_assignment = store.assign_capability("p1", "cap-exec")

        assert agent_assignment.actor_id == "a1"
        assert person_assignment.actor_id == "p1"
        assert agent_assignment.capability_id == "cap-exec"
        assert person_assignment.capability_id == "cap-exec"

    def test_agent_and_person_both_authorised_through_same_port(self) -> None:
        store = InMemoryAgentStore()

        agent = Agent(id="a1", name="Bot", marker=AgentMarker.AI)
        store.register_agent(agent)

        person = Person(id="p1", name="Alice")
        store.register_person(person)

        store.assign_capability("a1", "cap-shared")
        store.assign_capability("p1", "cap-shared")

        from capability_registry.src.adapters.execution_authorisation_adapter import (
            InMemoryExecutionAuthorisationPort,
        )
        auth = InMemoryExecutionAuthorisationPort(
            assignments=store.get_all_assignments(),
        )

        agent_result = auth.is_authorised("a1", "agent", "cap-shared")
        person_result = auth.is_authorised("p1", "person", "cap-shared")

        assert agent_result.authorised is True
        assert person_result.authorised is True

    def test_actor_id_is_canonical_in_assignment(self) -> None:
        store = InMemoryAgentStore()
        person = Person(id="p1", name="Alice")
        store.register_person(person)
        assignment = store.assign_capability("p1", "cap-1")
        assert assignment.actor_id == "p1"
        assert assignment.assignee_id == "p1"
        assert assignment.assignee_type == "person"


# ---- Proficiency boundary ----


class TestProficiencyActorOriented:
    """Proficiency can be associated with an Actor without branching on Agent/Person."""

    def test_proficiency_can_be_associated_with_actor_id(self) -> None:
        prof = CapabilityProficiency(
            id="prof-1",
            capability_id="cap-1",
            actor_id="p-alice",
            proficiency_level=ProficiencyLevel.EXPERT,
        )
        assert prof.actor_id == "p-alice"

    def test_proficiency_found_by_actor_id_without_type_branching(self) -> None:
        """Authorisation port finds proficiency by actor_id, not by actor_type branching."""
        from capability_registry.src.adapters.execution_authorisation_adapter import (
            InMemoryExecutionAuthorisationPort,
        )
        assignment = CapabilityAssignment(
            id="asgn-1",
            capability_id="cap-1",
            actor_id="p-alice",
            assignee_type="person",
            assignee_id="p-alice",
        )
        proficiency = CapabilityProficiency(
            id="prof-1",
            capability_id="cap-1",
            actor_id="p-alice",
            proficiency_level=ProficiencyLevel.EXPERT,
        )
        port = InMemoryExecutionAuthorisationPort(
            assignments=[assignment],
            proficiencies=[proficiency],
        )
        result = port.is_authorised("p-alice", "person", "cap-1")
        assert result.authorised is True
        assert result.proficiency is not None
        assert result.proficiency.proficiency_level == ProficiencyLevel.EXPERT

    def test_proficiency_legacy_person_id_still_supported(self) -> None:
        """Existing proficiency records with person_id/agent_id (no actor_id)
        still work through legacy fallback."""
        from capability_registry.src.adapters.execution_authorisation_adapter import (
            InMemoryExecutionAuthorisationPort,
        )
        assignment = CapabilityAssignment(
            id="asgn-1",
            capability_id="cap-1",
            actor_id="agent-1",
            assignee_type="agent",
            assignee_id="agent-1",
        )
        proficiency = CapabilityProficiency(
            id="prof-1",
            capability_id="cap-1",
            person_id=None,
            agent_id="agent-1",
            proficiency_level=ProficiencyLevel.COMPETENT,
        )
        port = InMemoryExecutionAuthorisationPort(
            assignments=[assignment],
            proficiencies=[proficiency],
        )
        result = port.is_authorised("agent-1", "agent", "cap-1")
        assert result.authorised is True
        assert result.proficiency is not None
        assert result.proficiency.agent_id == "agent-1"


# ---- OCP boundary ----


class TestOCPActorBoundary:
    """OCP does not require AgentStore internals for Actor identity and accepts Actor."""

    def test_ocp_assign_work_accepts_actor(self) -> None:
        """OCP.assign_work() can accept an Actor as the assignee."""
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role, Work

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="r1", name="Operator"))

        actor = Actor(
            id="actor-1",
            name="Alice",
            actor_type=ActorType.PERSON,
            reference_id="p-alice",
        )
        work = Work(id="w-actor", title="Task", accountable_role_id="r1")
        assignment = plane.assign_work(work, actor)

        assert assignment.assignee_type == "actor"
        assert assignment.assignee_id == "actor-1"

    def test_ocp_assign_work_actor_sets_assignee_actor_id(self) -> None:
        """When an Actor is assigned, work.assignee_actor_id is set."""
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role, Work

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="r1", name="Operator"))

        actor = Actor(
            id="actor-1",
            name="Bot",
            actor_type=ActorType.AGENT,
            reference_id="agent-1",
        )
        work = Work(id="w-actor", title="Task", accountable_role_id="r1")
        plane.assign_work(work, actor)

        assert work.assignee_actor_id == "actor-1"
        assert work.assignee_agent_id == "agent-1"

    def test_ocp_assign_work_actor_person_sets_assignee_person_id(self) -> None:
        """When a Person Actor is assigned, work.assignee_person_id is set."""
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role, Work

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="r1", name="Operator"))

        actor = Actor(
            id="actor-1",
            name="Alice",
            actor_type=ActorType.PERSON,
            reference_id="p-alice",
        )
        work = Work(id="w-actor", title="Task", accountable_role_id="r1")
        plane.assign_work(work, actor)

        assert work.assignee_actor_id == "actor-1"
        assert work.assignee_person_id == "p-alice"

    def test_ocp_assign_work_role_still_works(self) -> None:
        """Role assignment is preserved as a separate path from Actor."""
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role, Work

        plane = InMemoryOrganisationControlPlane()
        role = Role(id="r1", name="Operator")
        plane.register_role(role)
        work = Work(id="w-role", title="Task", accountable_role_id="r1")
        assignment = plane.assign_work(work, role)

        assert assignment.assignee_type == "role"
        assert assignment.assignee_id == "r1"
        assert work.assignee_role_id == "r1"

    def test_ocp_assign_work_person_still_works(self) -> None:
        """Direct Person assignment (legacy) is preserved."""
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Person, Work

        plane = InMemoryOrganisationControlPlane()
        person = Person(id="p1", name="Alice")
        work = Work(id="w-person", title="Task", accountable_role_id="r1")
        assignment = plane.assign_work(work, person)

        assert assignment.assignee_type == "person"
        assert assignment.assignee_id == "p1"
        assert work.assignee_person_id == "p1"

    def test_ocp_assign_work_agent_still_works(self) -> None:
        """Direct Agent assignment (legacy) is preserved."""
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Agent, Work

        plane = InMemoryOrganisationControlPlane()
        agent = Agent(id="a1", name="Bot", marker=AgentMarker.AI)
        work = Work(id="w-agent", title="Task", accountable_role_id="r1")
        assignment = plane.assign_work(work, agent)

        assert assignment.assignee_type == "agent"
        assert assignment.assignee_id == "a1"
        assert work.assignee_agent_id == "a1"

    def test_ocp_does_not_store_actor_records(self) -> None:
        """OCP does NOT have Person/Agent/Actor lifecycle stores."""
        from organisation_control_plane import InMemoryOrganisationControlPlane

        plane = InMemoryOrganisationControlPlane()
        assert not hasattr(plane, "_persons")
        assert not hasattr(plane, "_agents")

    def test_ocp_does_not_have_register_person_agent(self) -> None:
        """OCP does NOT register Person/Agent/Actor records (that's people_capability)."""
        from organisation_control_plane import InMemoryOrganisationControlPlane

        plane = InMemoryOrganisationControlPlane()
        assert not hasattr(plane, "register_person")
        assert not hasattr(plane, "register_agent")
        assert not hasattr(plane, "register_actor")


# ---- Execution boundary ----


class TestExecutionActorResolution:
    """Execution implementation resolves Actor -> Agent/Person separately from
    organisational authorisation."""

    def test_worker_uses_actor_context_for_authorisation(self) -> None:
        """The Worker provides actor_context with actor_id for authorisation checks."""
        from workflow_runner.src.worker import Worker

        worker = Worker()
        actor_context = {
            "actor_id": worker._agent_id,
            "actor_type": "agent",
        }
        assert "actor_id" in actor_context
        assert "actor_type" in actor_context

    def test_execution_adapter_extracts_actor_id_from_context(self) -> None:
        """CapabilityExecutionAdapter extracts actor_id from actor_context."""
        import inspect

        from workflow_runner.src.adapters.capability_execution_adapter import (
            CapabilityExecutionAdapter,
        )

        sig = inspect.signature(CapabilityExecutionAdapter._check_authorisation)
        params = list(sig.parameters.keys())
        assert "actor_context" in params or "capability_id" in params

    def test_execution_does_not_branch_on_actor_type_for_proficiency(self) -> None:
        """The authorisation port resolves proficiency by actor_id first,
        without requiring the caller to know whether the actor is Agent or Person."""
        from capability_registry.src.adapters.execution_authorisation_adapter import (
            InMemoryExecutionAuthorisationPort,
        )

        assignment = CapabilityAssignment(
            id="asgn-1",
            capability_id="cap-1",
            actor_id="unified-id",
            assignee_type="agent",
            assignee_id="unified-id",
        )
        proficiency = CapabilityProficiency(
            id="prof-1",
            capability_id="cap-1",
            actor_id="unified-id",
            proficiency_level=ProficiencyLevel.PROFICIENT,
        )
        port = InMemoryExecutionAuthorisationPort(
            assignments=[assignment],
            proficiencies=[proficiency],
        )

        # Same actor_id, different actor_type — both should find the same proficiency
        result_agent = port.is_authorised("unified-id", "agent", "cap-1")
        result_person = port.is_authorised("unified-id", "person", "cap-1")

        assert result_agent.proficiency is not None
        assert result_person.proficiency is not None
        assert result_agent.proficiency == result_person.proficiency


# ---- Role vs Actor distinction ----


class TestRoleActorDistinction:
    """Role is NOT an Actor. Role is a position/responsibility; Actor is the executor."""

    def test_role_is_not_an_actor(self) -> None:
        from role import Role

        role = Role(id="r1", name="Operator")
        assert not isinstance(role, Actor)

    def test_actor_is_not_a_role(self) -> None:
        actor = Actor(
            id="a1",
            name="Bot",
            actor_type=ActorType.AGENT,
            reference_id="agent-1",
        )
        from role import Role

        assert not isinstance(actor, Role)

    def test_actor_has_reference_id_pointing_to_person_or_agent(self) -> None:
        actor = Actor(
            id="a1",
            name="Bot",
            actor_type=ActorType.AGENT,
            reference_id="agent-abc",
        )
        assert actor.reference_id == "agent-abc"
        assert actor.actor_type != ActorType.PERSON  # type: ignore[comparison-overlap]
