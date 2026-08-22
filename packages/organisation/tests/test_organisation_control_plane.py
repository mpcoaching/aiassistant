"""
Tests for OrganisationControlPlane and InMemoryOrganisationControlPlane.
"""

from __future__ import annotations

from organisation_control_plane import (
    InMemoryOrganisationControlPlane,
    OrganisationControlPlane,
)
from role import Agent, Authority, Person, Role, RoleStatus, Work, WorkStatus


def test_interface_is_abstract() -> None:
    import pytest

    with pytest.raises(TypeError):
        OrganisationControlPlane()


def test_in_memory_plane_register_and_get_role() -> None:
    plane = InMemoryOrganisationControlPlane()
    role = Role(id="r1", name="Developer", authority_ids=["a1"])
    plane.register_role(role)
    assert plane.get_role("r1") == role
    assert plane.get_role("missing") is None


def test_in_memory_plane_list_roles() -> None:
    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="r1", name="A"))
    plane.register_role(Role(id="r2", name="B", status=RoleStatus.INACTIVE))
    active = plane.list_roles()
    assert len(active) == 1
    assert active[0].id == "r1"


def test_in_memory_plane_assign_work_to_role() -> None:
    plane = InMemoryOrganisationControlPlane()
    role = Role(id="r1", name="QA")
    plane.register_role(role)
    work = Work(id="w1", title="Test feature", requested_by_role_id="r1")
    assignment = plane.assign_work(work, role)
    assert assignment.work_id == "w1"
    assert assignment.assignee_type == "role"
    assert assignment.assignee_id == "r1"
    assert work.status == WorkStatus.ASSIGNED
    assert plane.get_work("w1") == work


def test_in_memory_plane_assign_work_to_person() -> None:
    plane = InMemoryOrganisationControlPlane()
    person = Person(id="p1", name="Alice")
    plane.register_person(person)
    work = Work(id="w2", title="Review PR")
    assignment = plane.assign_work(work, person)
    assert assignment.assignee_type == "person"
    assert assignment.assignee_id == "p1"
    assert work.assignee_person_id == "p1"


def test_in_memory_plane_assign_work_to_agent() -> None:
    plane = InMemoryOrganisationControlPlane()
    agent = Agent(id="a1", name="CI-Bot")
    plane.register_agent(agent)
    work = Work(id="w3", title="Run tests")
    assignment = plane.assign_work(work, agent)
    assert assignment.assignee_type == "agent"
    assert assignment.assignee_id == "a1"
    assert work.assignee_agent_id == "a1"


def test_in_memory_plane_get_work_missing() -> None:
    plane = InMemoryOrganisationControlPlane()
    assert plane.get_work("missing") is None


def test_in_memory_plane_delegate_authority() -> None:
    plane = InMemoryOrganisationControlPlane()
    from_role = Role(id="r1", name="Manager")
    to_role = Role(id="r2", name="Lead")
    authority = Authority(
        id="auth-1",
        name="Approve budget",
        scope="budget",
        grantor_role_id="r1",
        grantee_role_id="r2",
    )
    plane.register_role(from_role)
    plane.register_role(to_role)
    plane.register_authority(authority)
    delegation = plane.delegate_authority(from_role, to_role, authority)
    assert delegation.authority_id == "auth-1"
    assert delegation.from_role_id == "r1"
    assert delegation.to_role_id == "r2"


def test_in_memory_plane_organisational_context() -> None:
    plane = InMemoryOrganisationControlPlane()
    role = Role(id="r1", name="CEO", authority_ids=["auth-1", "auth-2"])
    plane.register_role(role)
    ctx = plane.get_organisational_context({"actor_id": "p1", "role_id": "r1"})
    assert ctx.current_actor_id == "p1"
    assert ctx.current_role_id == "r1"
    assert ctx.authority_scope == ["auth-1", "auth-2"]


def test_in_memory_plane_organisational_context_missing_role() -> None:
    plane = InMemoryOrganisationControlPlane()
    ctx = plane.get_organisational_context({"actor_id": "p1", "role_id": "missing"})
    assert ctx.current_role_id == "missing"
    assert ctx.authority_scope == []


def test_architectural_boundary_no_capability_methods() -> None:
    """OrganisationControlPlane must not expose capability-related methods."""
    forbidden = {
        "find_capability",
        "match_capability",
        "execute_capability",
        "execute_work",
        "run_agent",
        "invoke_tool",
    }
    for method in forbidden:
        assert not hasattr(OrganisationControlPlane, method), (
            f"OrganisationControlPlane must not have {method}"
        )
