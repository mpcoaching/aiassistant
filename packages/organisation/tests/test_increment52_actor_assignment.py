"""
Architectural + vertical-slice tests for Increment 52 — Explicit Actor Assignment
on Work Creation.

The organisational model already supports Actor assignment via OCP.assign_work.
This increment exposes that capability through the Work creation path by adding
``assignee_actor_id`` to ``WorkCreateRequest`` and wiring the ``WorkManagementAdapter``
to resolve the Actor through ``AgentStore`` and delegate to ``OCP.assign_work(work, actor)``.

Tests prove:
1.  Work creation without assignee_actor_id still works (backward compatibility).
2.  Work creation with a valid assignee_actor_id produces Work.assignee_actor_id == supplied ID.
3.  Both Person-backed and Agent-backed Actors can be assigned through the same mechanism.
4.  Invalid actor ID fails clearly and does not silently create unassigned Work.
5.  accountable_role_id remains distinct from assignee_actor_id.
6.  Existing OCP.assign_work authority semantics remain in force.
7.  Work events retain the correct assignee information.
8.  Operations can still observe/process the resulting Work.
9.  Increment 48 capability-development Work behaviour remains unchanged.
10. Existing WorkCreateRequest callers remain compatible.
"""

from __future__ import annotations

import os
import sys

import pytest
from actor import ActorType
from agent import Agent, AgentMarker, AgentStatus
from agent_store import InMemoryAgentStore
from contracts.organisational_events import WorkEvent, WorkEventType
from contracts.work_management import WorkCreateRequest
from person import Person, PersonStatus

from organisation_control_plane import InMemoryOrganisationControlPlane
from role import Role, Work, WorkStatus

ORGANISATION_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "src")
)
PEOPLE_CAPABILITY_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "people_capability", "src")
)

sys.path.insert(0, PEOPLE_CAPABILITY_SRC)
sys.path.insert(0, ORGANISATION_SRC)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# --------------------------------------------------------------------------- #
# A. Contract change
# --------------------------------------------------------------------------- #


def test_work_create_request_has_assignee_actor_id_field() -> None:
    """WorkCreateRequest includes assignee_actor_id as an optional field."""
    assert "assignee_actor_id" in WorkCreateRequest.model_fields
    field = WorkCreateRequest.model_fields["assignee_actor_id"]
    assert field.default is None


def test_work_create_request_assignee_actor_id_defaults_none() -> None:
    """WorkCreateRequest.assignee_actor_id is None by default."""
    req = WorkCreateRequest(
        title="Test",
        accountable_role_id="default",
    )
    assert req.assignee_actor_id is None


def test_existing_fields_remain_unchanged() -> None:
    """All existing WorkCreateRequest fields are preserved."""
    for name in (
        "title",
        "description",
        "accountable_role_id",
        "coordinating_role_id",
        "required_capability_ids",
        "develops_capability_id",
        "work_type",
        "priority",
        "organisation_id",
        "context",
    ):
        assert name in WorkCreateRequest.model_fields, f"missing field {name}"


# --------------------------------------------------------------------------- #
# B. Work creation without assignee_actor_id still works
# --------------------------------------------------------------------------- #


def test_work_management_adapter_accepts_request_without_actor_id() -> None:
    """Existing callers that omit assignee_actor_id still work."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))
    adapter = WorkManagementAdapter(plane)

    req = WorkCreateRequest(
        title="BAU task",
        accountable_role_id="default",
        work_type="bau",
        required_capability_ids=["cap-x"],
    )
    ref = adapter.create_work(req)
    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.status == WorkStatus.ASSIGNED
    assert work.assignee_actor_id is None


def test_work_management_adapter_existing_caller_path_unchanged() -> None:
    """The existing role-based assignment path produces the same behaviour."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="r1", name="Operator"))
    adapter = WorkManagementAdapter(plane)

    req = WorkCreateRequest(
        title="Project work",
        accountable_role_id="r1",
        work_type="project",
        required_capability_ids=[],
    )
    ref = adapter.create_work(req)
    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.assignee_role_id == "r1"
    assert work.assignee_actor_id is None


# --------------------------------------------------------------------------- #
# C. Work creation with valid assignee_actor_id
# --------------------------------------------------------------------------- #


def test_work_creation_with_agent_actor_assigns_actor_id() -> None:
    """Creating Work with a valid Agent-backed assignee_actor_id
    sets Work.assignee_actor_id to the supplied Actor ID."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))

    store = InMemoryAgentStore()
    agent = Agent(
        id="agent-1",
        name="Worker Agent",
        marker=AgentMarker.AI,
        status=AgentStatus.ACTIVE,
        fulfilled_role_ids=["default"],
    )
    store.register_agent(agent)
    actor = store.get_actor("agent-1")
    assert actor is not None

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Agent task",
        accountable_role_id="default",
        assignee_actor_id="agent-1",
        work_type="bau",
    )
    ref = adapter.create_work(req)
    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.assignee_actor_id == "agent-1"
    assert work.assignee_agent_id == "agent-1"
    assert work.status == WorkStatus.ASSIGNED


def test_work_creation_with_person_actor_assigns_actor_id() -> None:
    """Creating Work with a valid Person-backed assignee_actor_id
    sets Work.assignee_actor_id to the supplied Actor ID."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))

    store = InMemoryAgentStore()
    person = Person(
        id="person-1",
        name="Jane Doe",
        status=PersonStatus.ACTIVE,
        role_ids=["default"],
    )
    store.register_person(person)
    actor = store.get_actor("person-1")
    assert actor is not None
    assert actor.actor_type == ActorType.PERSON

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Person task",
        accountable_role_id="default",
        assignee_actor_id="person-1",
        work_type="bau",
    )
    ref = adapter.create_work(req)
    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.assignee_actor_id == "person-1"
    assert work.assignee_person_id == "person-1"
    assert work.status == WorkStatus.ASSIGNED


def test_work_creation_with_actor_assigns_accountable_role_distinct() -> None:
    """accountable_role_id (role accountability) and assignee_actor_id (concrete
    executor) remain distinct on the Work model."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="accountable-role", name="Accountable Role"))
    plane.register_role(Role(id="default", name="Default"))

    store = InMemoryAgentStore()
    agent = Agent(id="actor-x", name="Executor", marker=AgentMarker.AI)
    store.register_agent(agent)

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Distinct task",
        accountable_role_id="accountable-role",
        assignee_actor_id="actor-x",
        work_type="bau",
    )
    ref = adapter.create_work(req)
    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.accountable_role_id == "accountable-role"
    assert work.assignee_actor_id == "actor-x"
    assert work.accountable_role_id != work.assignee_actor_id


# --------------------------------------------------------------------------- #
# D. Invalid actor ID fails clearly
# --------------------------------------------------------------------------- #


def test_work_creation_with_unknown_actor_raises_clear_error() -> None:
    """An assignee_actor_id that does not exist in the store raises a
    clear ValueError — no Work is silently created unassigned."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))

    store = InMemoryAgentStore()

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Bad actor task",
        accountable_role_id="default",
        assignee_actor_id="nonexistent-actor",
        work_type="bau",
    )
    with pytest.raises(ValueError) as exc_info:
        adapter.create_work(req)
    assert "nonexistent-actor" in str(exc_info.value)
    # No work was created
    assert len(plane.list_work()) == 0


def test_work_creation_with_actor_id_no_store_raises() -> None:
    """If agent_store is not configured but assignee_actor_id is supplied,
    a clear error is raised."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))

    adapter = WorkManagementAdapter(plane, agent_store=None)

    req = WorkCreateRequest(
        title="No store task",
        accountable_role_id="default",
        assignee_actor_id="some-actor",
        work_type="bau",
    )
    with pytest.raises(ValueError) as exc_info:
        adapter.create_work(req)
    assert "AgentStore" in str(exc_info.value) or "not available" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# E. OCP.assign_work authority semantics preserved
# --------------------------------------------------------------------------- #


def test_assign_work_emits_assigned_event_with_actor_id() -> None:
    """When OCP.assign_work receives an Actor, the ASSIGNED event carries
    assignee_actor_id (Increment 44/45 semantics remain intact)."""
    plane = InMemoryOrganisationControlPlane()
    events: list = []
    plane.on_event(events.append)

    store = InMemoryAgentStore()
    agent = Agent(id="evt-agent", name="Event Agent", marker=AgentMarker.AI)
    store.register_agent(agent)
    actor = store.get_actor("evt-agent")

    work = Work(id="w-event", title="Event test", accountable_role_id="default")
    plane.assign_work(work, actor)

    assigned_events = [
        e for e in events
        if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED
    ]
    assert len(assigned_events) == 1
    assert assigned_events[0].assignee_actor_id == "evt-agent"


def test_existing_actor_assignment_mechanism_preserved() -> None:
    """OCP.assign_work still accepts Actor directly (not just through adapter)."""
    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()
    agent = Agent(id="direct-agent", name="Direct", marker=AgentMarker.AI)
    store.register_agent(agent)
    actor = store.get_actor("direct-agent")

    work = Work(id="w-direct", title="Direct", accountable_role_id="default")
    plane.assign_work(work, actor)

    assert work.assignee_actor_id == "direct-agent"
    assert work.status == WorkStatus.ASSIGNED


# --------------------------------------------------------------------------- #
# F. Work events retain correct assignee information
# --------------------------------------------------------------------------- #


def test_adapter_actor_assignment_event_has_actor_id() -> None:
    """Work creation with assignee_actor_id produces an ASSIGNED WorkEvent
    that carries the correct actor_id."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))
    events: list = []
    plane.on_event(events.append)

    store = InMemoryAgentStore()
    agent = Agent(id="evt-agent-2", name="Event Agent 2", marker=AgentMarker.AI)
    store.register_agent(agent)

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Event test adapter",
        accountable_role_id="default",
        assignee_actor_id="evt-agent-2",
        work_type="bau",
    )
    ref = adapter.create_work(req)

    assigned_events = [
        e for e in events
        if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED
    ]
    assert len(assigned_events) == 1
    assert assigned_events[0].assignee_actor_id == "evt-agent-2"
    assert assigned_events[0].work_id == ref.work_id


def test_adapter_role_assignment_event_has_no_actor_id() -> None:
    """Work creation without assignee_actor_id produces an ASSIGNED event
    where assignee_actor_id is None and assignee_role_id is set."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="r1", name="Operator"))
    events: list = []
    plane.on_event(events.append)

    adapter = WorkManagementAdapter(plane)

    req = WorkCreateRequest(
        title="Role test",
        accountable_role_id="r1",
        work_type="bau",
    )
    adapter.create_work(req)

    assigned_events = [
        e for e in events
        if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED
    ]
    assert len(assigned_events) == 1
    assert assigned_events[0].assignee_actor_id is None
    assert assigned_events[0].assignee_role_id == "r1"


# --------------------------------------------------------------------------- #
# G. Operations can still observe/process the resulting Work
# --------------------------------------------------------------------------- #


def test_operations_processes_actor_assigned_work() -> None:
    """Operations picks up READY work with assignee_actor_id set,
    without requiring a new execution path."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter
    from workflow_runner.src.operations import Operations

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))

    store = InMemoryAgentStore()
    agent = Agent(id="ops-agent", name="Ops Agent", marker=AgentMarker.AI)
    store.register_agent(agent)

    # Dummy execution results list
    executed: list[Work] = []

    class _DummyBackend:
        def can_handle(self, work: Work) -> bool:
            return True

        def execute(self, work: Work) -> dict:
            executed.append(work)
            return {"status": "completed", "outputs": {"summary": "done"}}

    Operations(
        org_plane=plane,
        backends=[_DummyBackend()],
        capability_registry=None,
    )

    adapter = WorkManagementAdapter(plane, agent_store=store)
    req = WorkCreateRequest(
        title="Ops actor work",
        accountable_role_id="default",
        assignee_actor_id="ops-agent",
        work_type="bau",
    )
    ref = adapter.create_work(req)

    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.status == WorkStatus.ASSIGNED
    assert work.assignee_actor_id == "ops-agent"

    # Mark ready triggers Operations which processes the work synchronously
    plane.mark_work_ready(ref.work_id)

    # Operations should have executed the work via the backend
    assert len(executed) == 1
    assert executed[0].assignee_actor_id == "ops-agent"

    # Work is now completed
    assert work.status == WorkStatus.COMPLETED


# --------------------------------------------------------------------------- #
# H. Increment 48 capability-development Work unaffected
# --------------------------------------------------------------------------- #


def test_increment48_develops_capability_id_unchanged() -> None:
    """assignee_actor_id is orthogonal to develops_capability_id —
    the Increment 48 identity chain is not weakened."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))

    store = InMemoryAgentStore()
    agent = Agent(id="cap-dev-agent", name="Cap Dev", marker=AgentMarker.AI)
    store.register_agent(agent)

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Develop capability: Gap Cap",
        accountable_role_id="default",
        assignee_actor_id="cap-dev-agent",
        work_type="capability_development",
        develops_capability_id="cap-gap-48-i52",
        required_capability_ids=["cap-helper"],
    )
    ref = adapter.create_work(req)
    work = plane.get_work(ref.work_id)
    assert work is not None
    assert work.develops_capability_id == "cap-gap-48-i52"
    assert work.required_capability_ids == ["cap-helper"]
    assert work.assignee_actor_id == "cap-dev-agent"
    # Required capability is NOT the same as developed capability
    assert "cap-gap-48-i52" not in work.required_capability_ids


# --------------------------------------------------------------------------- #
# I. Existing callers remain compatible
# --------------------------------------------------------------------------- #


def test_existing_caller_pattern_does_not_break() -> None:
    """The InMemoryWorkManagementPort (used by AI tests) still accepts
    WorkCreateRequest with assignee_actor_id absent."""
    req = WorkCreateRequest(
        title="Compatibility",
        description="test",
        accountable_role_id="default",
        work_type="project",
    )
    data = req.model_dump()
    assert data["assignee_actor_id"] is None
    assert "accountable_role_id" in data
    assert "develops_capability_id" in data


def test_existing_caller_pattern_can_include_assignee() -> None:
    """WorkCreateRequest accepts assignee_actor_id without breaking
    existing callers."""
    req = WorkCreateRequest(
        title="With actor",
        accountable_role_id="default",
        work_type="bau",
        assignee_actor_id="actor-123",
    )
    assert req.assignee_actor_id == "actor-123"


# --------------------------------------------------------------------------- #
# J. Lifecycle ordering: ASSIGNED before READY
# --------------------------------------------------------------------------- #


def test_actor_assigned_before_ready() -> None:
    """The lifecycle order is create → assign (ASSIGNED) → mark_ready (READY).
    The ASSIGNED event is emitted before the READY event."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))
    events: list = []
    plane.on_event(events.append)

    store = InMemoryAgentStore()
    agent = Agent(
        id="lifecycle-actor",
        name="Lifecycle Actor",
        marker=AgentMarker.AI,
        status=AgentStatus.ACTIVE,
        fulfilled_role_ids=["default"],
    )
    store.register_agent(agent)

    adapter = WorkManagementAdapter(plane, agent_store=store)

    req = WorkCreateRequest(
        title="Lifecycle test",
        accountable_role_id="default",
        assignee_actor_id="lifecycle-actor",
        work_type="bau",
    )
    ref = adapter.create_work(req)
    plane.mark_work_ready(ref.work_id)

    work_event_types = [
        e.event_type for e in events
        if isinstance(e, WorkEvent)
    ]
    assert WorkEventType.ASSIGNED in work_event_types
    assert WorkEventType.READY in work_event_types
    # ASSIGNED must come before READY
    assert work_event_types.index(WorkEventType.ASSIGNED) < work_event_types.index(WorkEventType.READY)
