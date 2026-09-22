"""
Tests for the Actor model and InMemoryAgentStore (Increment 24X).

Proves that:
- Actor unifies Person and Agent as an organisational identity
- The Assistant is registered as the first Agent/Actor
- Agent and Actor records are linked by reference_id
- InMemoryAgentStore provides lookup without storing Person/Agent lifecycle in OCP
"""

from __future__ import annotations

from actor import Actor, ActorType
from agent import Agent, AgentMarker, AgentStatus
from agent_store import InMemoryAgentStore


def test_actor_type_has_person_and_agent() -> None:
    assert ActorType.PERSON.value == "person"
    assert ActorType.AGENT.value == "agent"


def test_actor_creation_with_agent_reference() -> None:
    actor = Actor(
        id="agent-1",
        name="Bot",
        actor_type=ActorType.AGENT,
        reference_id="agent-1",
        marker="ai",
        fulfilled_role_ids=["researcher"],
    )
    assert actor.id == "agent-1"
    assert actor.actor_type == ActorType.AGENT
    assert actor.marker == "ai"
    assert "researcher" in actor.fulfilled_role_ids


def test_actor_creation_with_person_reference() -> None:
    actor = Actor(
        id="person-1",
        name="Alice",
        actor_type=ActorType.PERSON,
        reference_id="person-1",
    )
    assert actor.actor_type == ActorType.PERSON
    assert actor.marker is None


def test_in_memory_agent_store_register_and_get_agent() -> None:
    store = InMemoryAgentStore()
    agent = Agent(id="a1", name="Bot", marker=AgentMarker.AI)
    store.register_agent(agent)
    assert store.get_agent("a1") == agent
    assert store.get_agent("missing") is None


def test_register_agent_creates_corresponding_actor() -> None:
    store = InMemoryAgentStore()
    agent = Agent(id="a1", name="Bot", marker=AgentMarker.AI, fulfilled_role_ids=["r1"])
    store.register_agent(agent)
    actor = store.get_actor("a1")
    assert actor is not None
    assert actor.id == "a1"
    assert actor.name == "Bot"
    assert actor.actor_type == ActorType.AGENT
    assert actor.marker == "ai"
    assert actor.reference_id == "a1"
    assert "r1" in actor.fulfilled_role_ids


def test_list_actors_filtered_by_type() -> None:
    store = InMemoryAgentStore()
    agent = Agent(id="ag1", name="AgentA", marker=AgentMarker.AI)
    store.register_agent(agent)
    agents_only = store.list_actors(actor_type=ActorType.AGENT)
    persons = store.list_actors(actor_type=ActorType.PERSON)
    assert len(agents_only) == 1
    assert len(persons) == 0


def test_actor_fulfills_role() -> None:
    store = InMemoryAgentStore()
    agent, actor = InMemoryAgentStore.create_assistant_actor(
        actor_id="assistant",
        role_ids=["assistant", "researcher"],
    )
    store.register_agent(agent)
    assert store.actor_fulfills_role("assistant", "assistant")
    assert store.actor_fulfills_role("assistant", "researcher")
    assert not store.actor_fulfills_role("assistant", "ceo")


def test_find_actors_for_role() -> None:
    store = InMemoryAgentStore()
    agent_a, _ = InMemoryAgentStore.create_assistant_actor(
        actor_id="a1", role_ids=["researcher"]
    )
    agent_b, _ = InMemoryAgentStore.create_assistant_actor(
        actor_id="a2", role_ids=["researcher", "operator"]
    )
    store.register_agent(agent_a)
    store.register_agent(agent_b)
    holders = store.find_actors_for_role("researcher")
    assert len(holders) == 2
    holders_op = store.find_actors_for_role("operator")
    assert len(holders_op) == 1


class TestAssistantAsFirstActor:
    def test_assistant_agent_has_ai_marker(self) -> None:
        agent, actor = InMemoryAgentStore.create_assistant_actor()
        assert agent.marker == AgentMarker.AI
        assert agent.status == AgentStatus.ACTIVE
        assert actor.marker == "ai"

    def test_assistant_actor_type_is_agent(self) -> None:
        agent, actor = InMemoryAgentStore.create_assistant_actor()
        assert actor.actor_type == ActorType.AGENT

    def test_assistant_fulfills_assistant_role(self) -> None:
        agent, actor = InMemoryAgentStore.create_assistant_actor()
        assert "assistant" in actor.fulfilled_role_ids

    def test_assistant_actor_registered_in_store(self) -> None:
        store = InMemoryAgentStore()
        agent, actor = InMemoryAgentStore.create_assistant_actor()
        store.register_agent(agent)
        retrieved_agent = store.get_agent("assistant")
        retrieved_actor = store.get_actor("assistant")
        assert retrieved_agent is not None
        assert retrieved_agent.id == "assistant"
        assert retrieved_agent.name == "Assistant"
        assert retrieved_actor is not None
        assert retrieved_actor.actor_type == ActorType.AGENT
        assert retrieved_actor.marker == "ai"

    def test_assistant_actor_can_be_customized(self) -> None:
        agent, actor = InMemoryAgentStore.create_assistant_actor(
            actor_id="my-assistant",
            name="Custom Assistant",
            role_ids=["assistant", "researcher", "operator"],
        )
        assert agent.id == "my-assistant"
        assert agent.name == "Custom Assistant"
        assert actor.fulfilled_role_ids == ["assistant", "researcher", "operator"]


class TestCapabilityAssignmentContract:
    """Increment 28 — CapabilityAssignment links Actor to Capability.

    Proves:
    - CapabilityAssignment links Actor → Capability via actor_id
    - Assignment is distinct from Proficiency
    - Assignment can reference Skill and Tool IDs
    - Unassigned capability → not authorised
    - Assignment methods in InMemoryAgentStore work through normal mechanism
    """

    def test_capability_assignment_links_actor_to_capability(self) -> None:
        """CapabilityAssignment uses actor_id as the canonical link."""
        from capability_assignment import CapabilityAssignment, AssignmentType, AssignmentStatus

        assignment = CapabilityAssignment(
            id="asgn-1",
            capability_id="cap-1",
            actor_id="actor-1",
            assignment_type=AssignmentType.PRIMARY,
            status=AssignmentStatus.ACTIVE,
        )
        assert assignment.actor_id == "actor-1"
        assert assignment.capability_id == "cap-1"
        assert assignment.assignee_id == "actor-1"

    def test_assignment_is_distinct_from_proficiency(self) -> None:
        """Assignment ≠ Proficiency: one authorises, the other records evidence."""
        from capability_assignment import CapabilityAssignment
        from capability_proficiency import CapabilityProficiency, ProficiencyLevel

        assignment = CapabilityAssignment(
            id="asgn-1",
            capability_id="cap-1",
            actor_id="actor-1",
        )
        proficiency = CapabilityProficiency(
            id="prof-1",
            capability_id="cap-1",
            agent_id="actor-1",
            proficiency_level=ProficiencyLevel.EXPERT,
        )
        assert assignment is not proficiency
        assert assignment.__class__.__name__ != proficiency.__class__.__name__

    def test_assignment_can_reference_skills_and_tools(self) -> None:
        """CapabilityAssignment carries optional skill_ids and tool_ids references."""
        from capability_assignment import CapabilityAssignment

        assignment = CapabilityAssignment(
            id="asgn-1",
            capability_id="cap-1",
            actor_id="actor-1",
            skill_ids=["skill-1", "skill-2"],
            tool_ids=["tool-1"],
        )
        assert "skill-1" in assignment.skill_ids
        assert "tool-1" in assignment.tool_ids

    def test_assign_capability_requires_registered_actor(self) -> None:
        """Cannot assign capability to an Actor that doesn't exist in the store."""
        store = InMemoryAgentStore()
        import pytest
        with pytest.raises(KeyError):
            store.assign_capability("unknown-actor", "cap-1")

    def test_assign_capability_creates_assignment(self) -> None:
        """assign_capability creates a CapabilityAssignment linked to the Actor."""
        store = InMemoryAgentStore()
        agent, _ = InMemoryAgentStore.create_assistant_actor(
            actor_id="assistant",
            role_ids=["assistant"],
        )
        store.register_agent(agent)

        assignment = store.assign_capability(
            actor_id="assistant",
            capability_id="cap-knowledge",
        )
        assert assignment.actor_id == "assistant"
        assert assignment.capability_id == "cap-knowledge"
        assert assignment.status.value == "active"

    def test_get_assignments_for_actor(self) -> None:
        """get_assignments_for_actor returns all active assignments for an Actor."""
        store = InMemoryAgentStore()
        agent, _ = InMemoryAgentStore.create_assistant_actor(
            actor_id="assistant",
            role_ids=["assistant"],
        )
        store.register_agent(agent)
        store.assign_capability("assistant", "cap-1")
        store.assign_capability("assistant", "cap-2")

        assignments = store.get_assignments_for_actor("assistant")
        assert len(assignments) == 2
        cap_ids = [a.capability_id for a in assignments]
        assert "cap-1" in cap_ids
        assert "cap-2" in cap_ids

    def test_actor_has_capability_returns_true_when_assigned(self) -> None:
        store = InMemoryAgentStore()
        agent, _ = InMemoryAgentStore.create_assistant_actor(
            actor_id="assistant",
            role_ids=["assistant"],
        )
        store.register_agent(agent)
        store.assign_capability("assistant", "cap-1")
        assert store.actor_has_capability("assistant", "cap-1")

    def test_actor_has_capability_returns_false_when_not_assigned(self) -> None:
        store = InMemoryAgentStore()
        agent, _ = InMemoryAgentStore.create_assistant_actor(
            actor_id="assistant",
            role_ids=["assistant"],
        )
        store.register_agent(agent)
        assert not store.actor_has_capability("assistant", "unknown-cap")

    def test_capability_assignment_supports_skill_and_tool_ids(self) -> None:
        """Assignment created through store.assign_capability supports skill/tool refs."""
        store = InMemoryAgentStore()
        agent, _ = InMemoryAgentStore.create_assistant_actor(
            actor_id="assistant",
            role_ids=["assistant"],
        )
        store.register_agent(agent)
        assignment = store.assign_capability(
            "assistant",
            "cap-1",
            skill_ids=["skill-1"],
            tool_ids=["tool-1", "tool-2"],
        )
        assert assignment.skill_ids == ["skill-1"]
        assert assignment.tool_ids == ["tool-1", "tool-2" ]


class TestAssistantAsNormalActor:
    """Increment 28 — Assistant is a normal Actor, not a special entity."""

    def test_assistant_not_special_entity(self) -> None:
        """The Assistant is created via the same mechanism as any Agent."""
        store = InMemoryAgentStore()
        agent, actor, assignments = store.bootstrap_assistant(
            actor_id="assistant",
            role_ids=["assistant"],
            capability_ids=[],
        )
        assert agent.id == "assistant"
        assert actor.id == "assistant"
        assert actor.actor_type == ActorType.AGENT
        assert isinstance(agent, Agent)

    def test_assistant_capabilities_not_hardcoded(self) -> None:
        """The bootstrap does not hardcode a permanent list of Assistant capabilities."""
        store = InMemoryAgentStore()
        _, _, assignments = store.bootstrap_assistant(
            actor_id="assistant",
            role_ids=["assistant"],
            capability_ids=[],
        )
        assert assignments == []

    def test_assistant_capability_assignable_through_normal_mechanism(self) -> None:
        """Capabilities can be assigned to the Assistant through assign_capability."""
        store = InMemoryAgentStore()
        agent, _ = InMemoryAgentStore.create_assistant_actor(
            actor_id="assistant",
            role_ids=["assistant"],
        )
        store.register_agent(agent)
        assignment = store.assign_capability("assistant", "cap-research")
        assert assignment.actor_id == "assistant"
        assert assignment.capability_id == "cap-research"
        assert store.actor_has_capability("assistant", "cap-research")

    def test_assistant_bootstrap_with_capabilities(self) -> None:
        """bootstrap_assistant can assign initial capabilities through the normal mechanism."""
        store = InMemoryAgentStore()
        _, _, assignments = store.bootstrap_assistant(
            actor_id="assistant",
            role_ids=["assistant"],
            capability_ids=["cap-1", "cap-2"],
        )
        assert len(assignments) == 2
        assert store.actor_has_capability("assistant", "cap-1")
        assert store.actor_has_capability("assistant", "cap-2")
