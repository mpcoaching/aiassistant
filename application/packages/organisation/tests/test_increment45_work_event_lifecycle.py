"""
Regression tests for Increment 45 — _emit_work_event parameter cleanup.

These tests prove that:
  1. The ``assignee_id`` parameter has been removed from both
     ``InMemoryOrganisationControlPlane._emit_work_event`` and
     ``PaperclipOrganisationControlPlane._emit_work_event``.
  2. The emitted ``WorkEvent`` for ``ASSIGNED`` still carries the correct
     ``assignee_actor_id``, ``assignee_role_id``, and ``assignee_agent_id``
     — the data is read from the ``Work`` object, not from the removed
     parameter.
  3. No other event payloads, lifecycle semantics, or state transitions
     are affected.
"""

from __future__ import annotations

import inspect

import respx
from contracts.organisational_events import WorkEvent, WorkEventType
from httpx import Response
from organisation_paperclip import PaperclipOrganisationControlPlane

from organisation_control_plane import InMemoryOrganisationControlPlane
from role import Agent, Role, RoleStatus, Work, WorkStatus

# ============================================================================
# InMemory — parameter removed
# ============================================================================


def test_inmemory_emit_work_event_no_longer_accepts_assignee_id() -> None:
    """_emit_work_event signature no longer has assignee_id parameter."""
    sig = inspect.signature(InMemoryOrganisationControlPlane._emit_work_event)
    assert "assignee_id" not in sig.parameters


def test_inmemory_assigned_event_carries_actor_id_from_work() -> None:
    """assign_work to a Role emits ASSIGNED event with correct fields read from Work."""
    events: list = []
    org = InMemoryOrganisationControlPlane()
    org.on_event(events.append)

    role = Role(id="r-deploy", name="Deployer")
    org.register_role(role)
    work = Work(id="w-actor-cleanup", title="Deploy", accountable_role_id="r-deploy")

    org.assign_work(work, role)

    assigned = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED]
    assert len(assigned) == 1
    event = assigned[0]
    assert event.work_id == "w-actor-cleanup"
    assert event.status == WorkStatus.ASSIGNED.value
    assert event.assignee_role_id == "r-deploy"
    assert event.assignee_actor_id is None


def test_inmemory_assigned_event_carries_actor_id_when_assigned_to_actor() -> None:
    """assign_work to an Actor still populates assignee_actor_id on the event."""
    from actor import Actor, ActorType

    events: list = []
    org = InMemoryOrganisationControlPlane()
    org.on_event(events.append)

    actor = Actor(
        id="person-actor",
        name="Person Actor",
        actor_type=ActorType.PERSON,
        reference_id="p1",
    )
    work = Work(id="w-actor-id", title="Task", accountable_role_id="r1")
    org.register_role(Role(id="r1", name="Operator"))

    org.assign_work(work, actor)

    assigned = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED]
    assert len(assigned) == 1
    event = assigned[0]
    assert event.assignee_actor_id == "person-actor"
    assert event.assignee_agent_id is None


def test_inmemory_ready_event_payload_unchanged() -> None:
    """READY event is emitted with full Work payload — no assignee_id needed."""
    events: list = []
    org = InMemoryOrganisationControlPlane()
    org.on_event(events.append)

    role = Role(id="r1", name="Tester")
    org.register_role(role)
    work = Work(id="w-ready", title="Ready Test", accountable_role_id="r1")
    org.assign_work(work, role)
    events.clear()

    org.mark_work_ready(work.id)

    ready = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.READY]
    assert len(ready) == 1
    assert ready[0].work_id == "w-ready"
    assert ready[0].status == WorkStatus.READY.value


def test_inmemory_completed_event_payload_unchanged() -> None:
    """COMPLETED event payload unaffected by parameter removal."""
    events: list = []
    org = InMemoryOrganisationControlPlane()
    org.on_event(events.append)

    role = Role(id="r1", name="Tester")
    org.register_role(role)
    work = Work(id="w-done", title="Done", accountable_role_id="r1")
    org.assign_work(work, role)
    events.clear()

    outcome = {"result": "ok"}
    org.complete_work(work.id, outcome=outcome)

    completed = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.COMPLETED]
    assert len(completed) == 1
    assert completed[0].work_id == "w-done"
    assert completed[0].status == WorkStatus.COMPLETED.value
    assert completed[0].outcome == outcome


# ============================================================================
# Paperclip — parameter removed
# ============================================================================


def _make_paperclip_plane() -> PaperclipOrganisationControlPlane:
    return PaperclipOrganisationControlPlane(
        base_url="http://localhost:3100",
        api_key="test-key",
        company_id="test-org",
    )


def test_paperclip_emit_work_event_no_longer_accepts_assignee_id() -> None:
    """_emit_work_event signature no longer has assignee_id parameter."""
    sig = inspect.signature(PaperclipOrganisationControlPlane._emit_work_event)
    assert "assignee_id" not in sig.parameters


def test_paperclip_assigned_event_carries_assignee_from_work() -> None:
    """Paperclip assign_work emits ASSIGNED event with correct fields read from Work."""
    with respx.mock:
        respx.patch("http://localhost:3100/api/issues/w-agent").mock(
            return_value=Response(
                200,
                json={
                    "id": "w-agent",
                    "title": "Agent Task",
                    "status": "in_progress",
                    "assigneeAgentId": "agent-1",
                },
            )
        )
        plane = _make_paperclip_plane()
        events: list = []
        plane.on_event(events.append)

        agent = Agent(id="agent-1", name="Researcher", role_type="agent", status=RoleStatus.ACTIVE)
        work = Work(
            id="w-agent",
            title="Agent Task",
            work_type="task",
            status=WorkStatus.PENDING,
            accountable_role_id="unassigned",
            organisation_id="test-org",
        )

        plane.assign_work(work, agent)

        assigned = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED]
        assert len(assigned) == 1
        event = assigned[0]
        assert event.work_id == "w-agent"
        assert event.status == WorkStatus.ASSIGNED.value
        assert event.assignee_agent_id == "agent-1"
        plane.close()


def test_paperclip_created_event_payload_unchanged() -> None:
    """Paperclip create_work still emits CREATED event — parameter removal did not affect it."""
    with respx.mock:
        respx.post("http://localhost:3100/api/companies/test-org/issues").mock(
            return_value=Response(
                201,
                json={
                    "id": "issue-created",
                    "title": "New task",
                    "description": "Desc",
                    "status": "todo",
                    "priority": "medium",
                    "assigneeAgentId": None,
                    "capabilities": ["research"],
                    "createdAt": "2026-08-26T00:00:00Z",
                    "updatedAt": "2026-08-26T00:00:00Z",
                },
            )
        )
        plane = _make_paperclip_plane()
        events: list = []
        plane.on_event(events.append)

        plane.create_work(
            title="New task",
            description="Desc",
            required_capability_ids=["research"],
        )

        created = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.CREATED]
        assert len(created) == 1
        assert created[0].work_id == "issue-created"
        assert created[0].status == WorkStatus.PENDING.value
        plane.close()
