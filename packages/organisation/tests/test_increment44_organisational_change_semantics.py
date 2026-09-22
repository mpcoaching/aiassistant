"""
Increment 44 — Organisational Change Semantics: defect fixes and regression.

Three confirmed defects addressed:

1. explain_implementation() conflated Actor IDs with Role IDs.
   Fix: no longer calls get_role(actor_id); Actor presence is determined
   solely by Work assignment.

2. WorkEvent dropped assignee_actor_id when work was assigned to an Actor.
   Fix: WorkEvent now has assignee_actor_id field; both InMemory and Paperclip
   _emit_work_event populate it from work.assignee_actor_id.

3. _has_organisational_authority() checked only that an Authority record
   existed, not that it was actually delegated to the role.
   Fix: now requires a Delegation record with matching authority_id and
   to_role_id == role.id.
"""

from __future__ import annotations

import os
import sys

from actor import Actor, ActorType
from agent import Agent
from agent_store import InMemoryAgentStore
from contracts.organisational_events import WorkEvent, WorkEventType

from organisation_control_plane import InMemoryOrganisationControlPlane
from role import (
    Authority,
    Role,
    RoleStatus,
    Work,
    WorkStatus,
)

ORGANISATION_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "src")
)
PEOPLE_CAPABILITY_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "people_capability", "src")
)
PAPERCLIP_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "organisation_paperclip", "src")
)

sys.path.insert(0, PEOPLE_CAPABILITY_SRC)
sys.path.insert(0, ORGANISATION_SRC)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================================
# Defect 1 — explain_implementation Actor/Role conflation
# ============================================================================


def test_explain_implementation_actor_with_no_work_returns_none() -> None:
    """An Actor with no work returns None — no fallback to get_role()."""
    plane = InMemoryOrganisationControlPlane()
    assert plane.explain_implementation("nonexistent-actor") is None


def test_explain_implementation_role_id_collision_does_not_impersonate_actor() -> None:
    """A Role registered with an ID that matches an Actor ID must not cause
    explain_implementation() to return a non-None result for that Actor ID
    when the Actor has no work assigned."""
    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="specialist", name="Some Role"))
    result = plane.explain_implementation("specialist")
    assert result is None


def test_explain_implementation_returns_explanation_when_work_assigned() -> None:
    """An Actor with assigned work gets a proper explanation."""
    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    operator = Role(id="o", name="Operator", authority_ids=["auth1"],
                   status=RoleStatus.ACTIVE)
    plan_authority = Authority(id="auth1", name="Execute",
                               scope="execute-organisational-change",
                               grantor_role_id="f", grantee_role_id="o")
    founder = Role(id="f", name="Founder", authority_ids=["auth1"],
                   status=RoleStatus.ACTIVE)
    plane.register_role(founder)
    plane.register_role(operator)
    plane.register_authority(plan_authority)
    plane.delegate_authority(founder, operator, plan_authority)

    agent = Agent(id="specialist", name="Specialist", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("specialist")

    work = Work(id="w1", title="Change", accountable_role_id="o",
                required_capability_ids=[], status=WorkStatus.PENDING)
    plane.execute_organisational_change(work=work, assignee=actor, role=operator)

    explanation = plane.explain_implementation("specialist")
    assert explanation is not None
    assert explanation["actor_id"] == "specialist"
    assert len(explanation["assigned_work"]) == 1
    assert explanation["assigned_work"][0]["work_id"] == "w1"
    assert explanation["accountable_roles"] == ["o"]


# ============================================================================
# Defect 2 — WorkEvent preserves assignee_actor_id
# ============================================================================


def test_work_event_has_assignee_actor_id_field() -> None:
    """WorkEvent model now includes assignee_actor_id field."""
    event = WorkEvent(
        event_type=WorkEventType.ASSIGNED,
        work_id="w-actor-test",
        title="Actor Assigned",
        status="assigned",
        assignee_actor_id="actor-42",
    )
    assert event.assignee_actor_id == "actor-42"


def test_assign_work_to_person_actor_emits_event_with_actor_id() -> None:
    """When Work is assigned to a PERSON Actor, the emitted WorkEvent carries
    assignee_actor_id."""
    plane = InMemoryOrganisationControlPlane()
    events: list = []
    plane.on_event(lambda e: events.append(e))

    person_actor = Actor(
        id="person-actor",
        name="Person Actor",
        actor_type=ActorType.PERSON,
        reference_id="p1",
    )
    work = Work(id="w-person", title="Person Task", accountable_role_id="r1")
    plane.register_role(Role(id="r1", name="Operator"))

    plane.assign_work(work, person_actor)

    assigned_events = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED]
    assert len(assigned_events) >= 1
    last = assigned_events[-1]
    assert last.assignee_actor_id == "person-actor"
    assert work.assignee_actor_id == "person-actor"
    assert work.assignee_person_id == "p1"


def test_assign_work_to_agent_actor_preserves_actor_id() -> None:
    """When Work is assigned to an AGENT Actor, the event carries
    assignee_actor_id and assignee_agent_id."""
    plane = InMemoryOrganisationControlPlane()
    events: list = []
    plane.on_event(lambda e: events.append(e))

    agent_actor = Actor(
        id="agent-actor",
        name="Agent Actor",
        actor_type=ActorType.AGENT,
        reference_id="a1",
    )
    work = Work(id="w-agent", title="Agent Task", accountable_role_id="r1")
    plane.register_role(Role(id="r1", name="Operator"))

    plane.assign_work(work, agent_actor)

    assigned_events = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED]
    assert len(assigned_events) >= 1
    last = assigned_events[-1]
    assert last.assignee_actor_id == "agent-actor"
    assert last.assignee_agent_id == "a1"


def test_assign_work_to_role_preserves_role_id_no_actor_id() -> None:
    """When Work is assigned to a Role, the event has assignee_role_id
    and assignee_actor_id is None."""
    plane = InMemoryOrganisationControlPlane()
    events: list = []
    plane.on_event(lambda e: events.append(e))

    role = Role(id="r-deploy", name="Deployer")
    plane.register_role(role)
    work = Work(id="w-role", title="Deploy", accountable_role_id="r-deploy")

    plane.assign_work(work, role)

    assigned_events = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED]
    assert len(assigned_events) >= 1
    last = assigned_events[-1]
    assert last.assignee_role_id == "r-deploy"
    assert last.assignee_actor_id is None


def test_assign_work_to_person_directly_preserves_actor_id() -> None:
    """Person Actors retain their Actor identity in the event."""
    plane = InMemoryOrganisationControlPlane()
    events: list = []
    plane.on_event(lambda e: events.append(e))

    person_actor = Actor(
        id="person-7",
        name="Jane Developer",
        actor_type=ActorType.PERSON,
        reference_id="p7",
    )
    work = Work(id="w-person-direct", title="Code Review", accountable_role_id="r-cr")
    plane.register_role(Role(id="r-cr", name="Code Reviewer"))

    plane.assign_work(work, person_actor)

    assigned_events = [e for e in events if isinstance(e, WorkEvent) and e.event_type == WorkEventType.ASSIGNED]
    assert len(assigned_events) >= 1
    last = assigned_events[-1]
    assert last.assignee_actor_id == "person-7"
    assert last.assignee_agent_id is None


# ============================================================================
# Defect 3 — _has_organisational_authority delegation verification
# ============================================================================


def _setup_founder_operator(plane, with_delegation=True):
    """Helper: register founder + operator roles, authority, and optionally delegation."""
    founder = Role(id="f", name="Founder", authority_ids=["auth1"],
                   status=RoleStatus.ACTIVE)
    operator = Role(id="o", name="Operator", authority_ids=["auth1"],
                    status=RoleStatus.ACTIVE)
    authority = Authority(
        id="auth1", name="Execute",
        scope="execute-organisational-change",
        grantor_role_id="f", grantee_role_id="o",
    )
    plane.register_role(founder)
    plane.register_role(operator)
    plane.register_authority(authority)
    if with_delegation:
        plane.delegate_authority(founder, operator, authority)
    return founder, operator, authority


def test_authority_exists_no_delegation_rejected() -> None:
    """Authority record exists but no Delegation → unauthorised."""
    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    _setup_founder_operator(plane, with_delegation=False)

    agent = Agent(id="a1", name="Agent", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("a1")

    work = Work(id="w-no-deleg", title="Work", accountable_role_id="o",
                status=WorkStatus.PENDING)
    result = plane.execute_organisational_change(work=work, assignee=actor, role=plane.get_role("o"))
    assert result["status"] == "unauthorised"
    assert result["authority_checked"] is True


def test_authority_wrong_grantee_rejected() -> None:
    """Authority granted to a different role → unauthorised."""
    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder = Role(id="f", name="Founder", authority_ids=["auth1"],
                   status=RoleStatus.ACTIVE)
    other = Role(id="other", name="Other", authority_ids=[],
                 status=RoleStatus.ACTIVE)
    operator = Role(id="o", name="Operator", authority_ids=["auth1"],
                    status=RoleStatus.ACTIVE)
    authority = Authority(
        id="auth1", name="Execute",
        scope="execute-organisational-change",
        grantor_role_id="f", grantee_role_id="other",
    )
    plane.register_role(founder)
    plane.register_role(other)
    plane.register_role(operator)
    plane.register_authority(authority)
    plane.delegate_authority(founder, other, authority)

    agent = Agent(id="a1", name="Agent", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("a1")

    work = Work(id="w-wrong-grantee", title="Work", accountable_role_id="o",
                status=WorkStatus.PENDING)
    result = plane.execute_organisational_change(work=work, assignee=actor, role=operator)
    assert result["status"] == "unauthorised"
    assert result["authority_checked"] is True


def test_valid_delegation_accepted() -> None:
    """Valid Delegation → executed."""
    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    _setup_founder_operator(plane, with_delegation=True)

    agent = Agent(id="a1", name="Agent", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("a1")

    work = Work(id="w-valid-deleg", title="Work", accountable_role_id="o",
                status=WorkStatus.PENDING)
    result = plane.execute_organisational_change(work=work, assignee=actor, role=plane.get_role("o"))
    assert result["status"] == "executed"


def test_unauthorised_role_rejected() -> None:
    """Role with no authority_ids → unauthorised."""
    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    no_auth = Role(id="no-auth", name="No Auth", authority_ids=[],
                   status=RoleStatus.ACTIVE)
    plane.register_role(no_auth)

    agent = Agent(id="a1", name="Agent", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("a1")

    work = Work(id="w-no-auth", title="Work", accountable_role_id="no-auth",
                status=WorkStatus.PENDING)
    result = plane.execute_organisational_change(work=work, assignee=actor, role=no_auth)
    assert result["status"] == "unauthorised"


def test_increment43_delegated_authority_still_succeeds() -> None:
    """Existing Increment 43 delegated-authority path still works after the fix."""
    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder = Role(id="founder", name="Founder", authority_ids=["auth-execute-change"],
                   status=RoleStatus.ACTIVE)
    ca_role = Role(id="customer-acquisition", name="Customer Acquisition",
                   required_capability_ids=["demand-generation"],
                   authority_ids=["auth-execute-change"], status=RoleStatus.ACTIVE)
    plane.register_role(founder)
    plane.register_role(ca_role)
    authority = Authority(
        id="auth-execute-change", name="Execute organisational change",
        scope="execute-organisational-change",
        grantor_role_id="founder", grantee_role_id="customer-acquisition",
    )
    plane.register_authority(authority)
    plane.delegate_authority(founder, ca_role, authority)

    agent = Agent(id="specialist", name="Specialist", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("specialist")
    assert actor is not None
    assert actor.actor_type == ActorType.AGENT

    work = Work(id="w-prove-delegation-still-works", title="Add capacity",
                accountable_role_id="customer-acquisition",
                required_capability_ids=["demand-generation"],
                status=WorkStatus.PENDING)
    result = plane.execute_organisational_change(
        work=work, assignee=actor, role=ca_role,
        capability_ids=["demand-generation"],
    )
    assert result["status"] == "executed"
    assert result["authority_checked"] is True
