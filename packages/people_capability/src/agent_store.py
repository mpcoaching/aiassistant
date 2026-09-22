"""
People/Capability domain — InMemoryAgentStore (Increment 24X, extended Increment 28).

In-memory store for Agent, Actor, and CapabilityAssignment records within the
people_capability plane. Does not depend on the organisation or operations
layers.

Agent records are the authoritative software-entity records. Actor records
are lightweight organisational identities derived from Agent/Person records.
CapabilityAssignment records link Actors to Capabilities (with proficiency
tracked separately via CapabilityProficiency).
"""

from __future__ import annotations

from typing import Any

from agent import Agent, AgentMarker, AgentStatus
from actor import Actor, ActorType
from capability_assignment import (
    AssignmentStatus,
    CapabilityAssignment,
)
from person import Person, PersonStatus


class InMemoryAgentStore:
    """In-memory store for Agent records and Actor identities.

    Owns the Assistant as the first registered Agent/Actor.
    The organisation layer references agents by ID; this store
    holds the authoritative Agent and Actor lifecycle records.

    Also manages CapabilityAssignment records that link Actors to
    Capabilities — assignments are an explicit step in the learning
    loop between capability existence and capability exercise.
    """

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._persons: dict[str, Person] = {}
        self._actors: dict[str, Actor] = {}
        self._assignments: dict[str, CapabilityAssignment] = {}

    # ---- Agent records ----

    def register_agent(self, agent: Agent) -> Agent:
        """Register a software entity as an Agent."""
        self._agents[agent.id] = agent
        actor = Actor(
            id=agent.id,
            name=agent.name,
            actor_type=ActorType.AGENT,
            reference_id=agent.id,
            marker=agent.marker.value if agent.marker else None,
            fulfilled_role_ids=list(agent.fulfilled_role_ids),
            organisation_id=agent.metadata.get("organisation_id", "default"),
            metadata=agent.metadata,
        )
        self._actors[agent.id] = actor
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[Agent]:
        return [a for a in self._agents.values() if a.status == AgentStatus.ACTIVE]

    def register_person(self, person: Person) -> Person:
        """Register a human entity as a Person and create its Actor identity.

        The Person record is stored as the authoritative human-entity record.
        A corresponding Actor is created with ``ActorType.PERSON`` and
        ``reference_id`` pointing to the Person's ID.  The Actor shares the
        Person's name and role information, but the full Person record is not
        duplicated.

        The returned Actor can be assigned capabilities through the same
        ``assign_capability`` mechanism used for Agents.
        """
        self._persons[person.id] = person
        actor = Actor(
            id=person.id,
            name=person.name,
            actor_type=ActorType.PERSON,
            reference_id=person.id,
            marker=None,
            fulfilled_role_ids=list(person.role_ids),
            organisation_id=person.metadata.get("organisation_id", "default"),
            metadata=person.metadata,
        )
        self._actors[person.id] = actor
        return person

    def get_person(self, person_id: str) -> Person | None:
        return self._persons.get(person_id)

    def list_persons(self) -> list[Person]:
        return [p for p in self._persons.values() if p.status == PersonStatus.ACTIVE]

    # ---- Actor identities ----

    def get_actor(self, actor_id: str) -> Actor | None:
        """Retrieve an Actor identity by ID."""
        return self._actors.get(actor_id)

    def list_actors(self, actor_type: ActorType | None = None) -> list[Actor]:
        """List all Actor identities, optionally filtered by type."""
        actors = list(self._actors.values())
        if actor_type is not None:
            actors = [a for a in actors if a.actor_type == actor_type]
        return actors

    def actor_fulfills_role(self, actor_id: str, role_id: str) -> bool:
        """Check whether an actor fulfills a given role."""
        actor = self._actors.get(actor_id)
        if actor is None:
            return False
        return role_id in actor.fulfilled_role_ids

    def find_actors_for_role(self, role_id: str) -> list[Actor]:
        """Return all actors that fulfill a given role."""
        return [a for a in self._actors.values() if role_id in a.fulfilled_role_ids]

    # ---- Capability assignments ----

    def assign_capability(
        self,
        actor_id: str,
        capability_id: str,
        skill_ids: list[str] | None = None,
        tool_ids: list[str] | None = None,
        assignment_type: Any | None = None,
        status: AssignmentStatus = AssignmentStatus.ACTIVE,
        **kwargs: Any,
    ) -> CapabilityAssignment:
        """Assign a Capability to an Actor through the normal organisational mechanism.

        Creates a CapabilityAssignment record linking the Actor to the Capability.
        Skills and Tools are referenced by ID only — no implementation coupling.
        """
        from capability_assignment import AssignmentType

        if actor_id not in self._actors:
            raise KeyError(
                f"Cannot assign capability: Actor '{actor_id}' not found in store"
            )

        actor = self._actors[actor_id]
        assignment = CapabilityAssignment(
            id=kwargs.get("assignment_id", f"assign-{actor_id}-{capability_id}"),
            capability_id=capability_id,
            actor_id=actor_id,
            assignee_type=actor.actor_type.value,
            assignee_id=actor_id,
            skill_ids=skill_ids or [],
            tool_ids=tool_ids or [],
            assignment_type=assignment_type or AssignmentType.PRIMARY,
            status=status,
            authorised_by=kwargs.get("authorised_by"),
            reason=kwargs.get("reason", ""),
            metadata=kwargs.get("metadata", {}),
        )
        self._assignments[assignment.id] = assignment
        return assignment

    def get_assignment(self, assignment_id: str) -> CapabilityAssignment | None:
        """Retrieve a capability assignment by ID."""
        return self._assignments.get(assignment_id)

    def get_assignments_for_actor(self, actor_id: str) -> list[CapabilityAssignment]:
        """Return all capability assignments for an Actor."""
        return [
            a for a in self._assignments.values()
            if (a.actor_id or a.assignee_id) == actor_id and a.status == AssignmentStatus.ACTIVE
        ]

    def get_assignments_for_capability(self, capability_id: str) -> list[CapabilityAssignment]:
        """Return all capability assignments for a given Capability."""
        return [
            a for a in self._assignments.values()
            if a.capability_id == capability_id and a.status == AssignmentStatus.ACTIVE
        ]

    def actor_has_capability(self, actor_id: str, capability_id: str) -> bool:
        """Check whether an Actor is assigned an active Capability."""
        return any(
            a.capability_id == capability_id and a.status == AssignmentStatus.ACTIVE
            for a in self._assignments.values()
            if (a.actor_id or a.assignee_id) == actor_id
        )

    def get_all_assignments(self) -> list[CapabilityAssignment]:
        """Return all capability assignments."""
        return list(self._assignments.values())

    # ---- Bootstrap ----

    @staticmethod
    def create_assistant_actor(
        actor_id: str = "assistant",
        role_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> tuple[Agent, Actor]:
        """Create the canonical Assistant Agent and its Actor identity.

        The Assistant is an Agent with an Actor identity — not a special
        organisational entity.  Capabilities are **not** hardcoded here;
        they are assigned through the normal ``assign_capability`` mechanism
        after registration (see :meth:`bootstrap_assistant`).
        """
        if role_ids is None:
            role_ids = ["assistant"]

        agent = Agent(
            id=actor_id,
            name=kwargs.get("name", "Assistant"),
            marker=AgentMarker.AI,
            status=AgentStatus.ACTIVE,
            fulfilled_role_ids=role_ids,
            runtime_identity=kwargs.get("runtime_identity", "chat"),
            metadata={
                "organisation_id": kwargs.get("organisation_id", "default"),
                "actor_type": "agent",
            },
        )
        actor = Actor(
            id=agent.id,
            name=agent.name,
            actor_type=ActorType.AGENT,
            reference_id=agent.id,
            marker=agent.marker.value,
            fulfilled_role_ids=list(agent.fulfilled_role_ids),
            organisation_id=agent.metadata.get("organisation_id", "default"),
            metadata=agent.metadata,
        )
        return agent, actor

    def bootstrap_assistant(
        self,
        actor_id: str = "assistant",
        role_ids: list[str] | None = None,
        capability_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> tuple[Agent, Actor, list[CapabilityAssignment]]:
        """Bootstrap the Assistant Actor + Agent + capability assignments.

        Creates the Assistant Agent and Actor via ``create_assistant_actor``,
        registers the Agent in this store, then assigns each listed capability
        through the normal ``assign_capability`` mechanism.

        Capabilities are **not** hardcoded — callers pass the capability IDs
        that should be assigned at bootstrap time.  In production these would
        come from organisational configuration or the capability registry.
        """
        agent, actor = InMemoryAgentStore.create_assistant_actor(
            actor_id=actor_id,
            role_ids=role_ids,
            **kwargs,
        )
        self.register_agent(agent)

        assignments: list[CapabilityAssignment] = []
        for cap_id in capability_ids or []:
            self.assign_capability(actor.id, cap_id)
            assignments.append(self._assignments[f"assign-{actor.id}-{cap_id}"])

        return agent, actor, assignments
