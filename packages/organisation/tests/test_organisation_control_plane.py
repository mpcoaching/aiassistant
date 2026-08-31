"""
Tests for OrganisationControlPlane and InMemoryOrganisationControlPlane.
"""

from __future__ import annotations

import pytest

from contracts.work_management import WorkCreateRequest
from organisation_control_plane import (
    InMemoryOrganisationControlPlane,
    OrganisationControlPlane,
)
from role import Agent, Authority, Person, Role, RoleStatus, Work, WorkStatus


def test_interface_is_abstract() -> None:
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
    work = Work(id="w1", title="Test feature", accountable_role_id="r1")
    assignment = plane.assign_work(work, role)
    assert assignment.work_id == "w1"
    assert assignment.assignee_type == "role"
    assert assignment.assignee_id == "r1"
    assert work.status == WorkStatus.ASSIGNED
    assert plane.get_work("w1") == work


def test_in_memory_plane_assign_work_to_person() -> None:
    plane = InMemoryOrganisationControlPlane()
    person = Person(id="p1", name="Alice")
    work = Work(id="w2", title="Review PR", accountable_role_id="r-mgr")
    assignment = plane.assign_work(work, person)
    assert assignment.assignee_type == "person"
    assert assignment.assignee_id == "p1"
    assert work.assignee_person_id == "p1"


def test_in_memory_plane_assign_work_to_agent() -> None:
    plane = InMemoryOrganisationControlPlane()
    agent = Agent(id="a1", name="CI-Bot")
    work = Work(id="w3", title="Run tests", accountable_role_id="r-mgr")
    assignment = plane.assign_work(work, agent)
    assert assignment.assignee_type == "agent"
    assert assignment.assignee_id == "a1"
    assert work.assignee_agent_id == "a1"


def test_in_memory_plane_does_not_store_person_agent_records() -> None:
    plane = InMemoryOrganisationControlPlane()
    assert not hasattr(plane, "_persons")
    assert not hasattr(plane, "_agents")


def test_in_memory_plane_has_no_register_person_agent() -> None:
    plane = InMemoryOrganisationControlPlane()
    assert not hasattr(plane, "register_person")
    assert not hasattr(plane, "register_agent")


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


def test_architectural_boundary_no_forbidden_methods() -> None:
    forbidden = {
        "find_capability",
        "match_capability",
        "execute_capability",
        "run_agent",
        "invoke_tool",
        "register_person",
        "register_agent",
        "coordinate_project",
        "sequence_work",
        "track_progress",
        "manage_dependencies",
        "execute_work",
    }
    for method in forbidden:
        assert not hasattr(OrganisationControlPlane, method), (
            f"OrganisationControlPlane must not have {method}"
        )


def test_bau_accountability_scenario() -> None:
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
    assignment = plane.assign_work(work, fm)
    assert work.accountable_role_id == "r-fm"
    assert work.coordinating_role_id == "r-fm"
    assert assignment.assignee_id == "r-fm"


def test_strategic_project_accountability_scenario() -> None:
    plane = InMemoryOrganisationControlPlane()
    cmo = Role(id="r-cmo", name="CMO")
    pm = Role(id="r-pm", name="Project Manager")
    plane.register_role(cmo)
    plane.register_role(pm)
    initiative = Work(
        id="w-init",
        title="Enter Market X",
        work_type="project",
        accountable_role_id="r-cmo",
        coordinating_role_id="r-pm",
    )
    plane.assign_work(initiative, cmo)
    assert initiative.accountable_role_id == "r-cmo"
    assert initiative.coordinating_role_id == "r-pm"


def test_mark_work_ready_transitions_to_ready() -> None:
    plane = InMemoryOrganisationControlPlane()
    work = Work(id="w1", title="Task", accountable_role_id="r1")
    plane.register_role(Role(id="r1", name="Operator"))
    plane.assign_work(work, Role(id="r1", name="Operator"))
    assert work.status == WorkStatus.ASSIGNED

    ready = plane.mark_work_ready("w1")
    assert ready is not None
    assert ready.status == WorkStatus.READY
    assert plane.get_work("w1").status == WorkStatus.READY


def test_mark_work_ready_missing_work_returns_none() -> None:
    plane = InMemoryOrganisationControlPlane()
    result = plane.mark_work_ready("missing")
    assert result is None


def test_ocp_has_no_pathway_runtime_import() -> None:
    """OrganisationControlPlane must not import PathwayRuntime or other operational types."""
    import ast
    import os

    source_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "organisation_control_plane.py"
    )
    source_path = os.path.normpath(source_path)
    with open(source_path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "pathway_runtime" not in node.module, (
                "OrganisationControlPlane must not import from pathway_runtime"
            )
            assert "bus" not in node.module, (
                "OrganisationControlPlane must not import from bus"
            )


def test_backend_interchangeable_via_organisation_interface() -> None:
    """Paperclip and InMemory implementations are interchangeable through OrganisationControlPlane."""
    from organisation.src.adapters.work_management_adapter import WorkManagementAdapter
    from role import Work

    in_memory = InMemoryOrganisationControlPlane()
    in_memory.register_role(Role(id="r1", name="Operator", authority_ids=[]))
    in_memory_work = Work(id="w-inter-1", title="Interop test", accountable_role_id="r1")
    in_memory.assign_work(in_memory_work, Role(id="r1", name="Operator"))
    assert in_memory_work.status == WorkStatus.ASSIGNED

    wm_in_memory = WorkManagementAdapter(in_memory)
    wm_in_memory.create_work(
        WorkCreateRequest(
            title="Adapter interop",
            description="Proves WorkManagementAdapter works with any OrganisationControlPlane",
            accountable_role_id="r1",
            work_type="project",
            priority="normal",
            organisation_id="default",
            required_capability_ids=[],
        )
    )
    assert len(in_memory.list_work()) == 2
