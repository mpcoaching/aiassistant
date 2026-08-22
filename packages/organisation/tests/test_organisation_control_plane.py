"""
Tests for OrganisationControlPlane and InMemoryOrganisationControlPlane.
"""

from __future__ import annotations

from typing import Any

import pytest
from pathway_runtime import PathwayCallRequest, PathwayResponse, PathwayRuntime, PathwayStatus

from organisation_control_plane import (
    InMemoryOrganisationControlPlane,
    OrganisationControlPlane,
)
from role import Agent, Authority, Person, Role, RoleStatus, Work, WorkStatus


class MockRuntime(PathwayRuntime):
    """Mock PathwayRuntime for testing execute_work."""

    def __init__(self, response: PathwayResponse | None = None) -> None:
        self._response = response or PathwayResponse(
            status=PathwayStatus.COMPLETED,
            outputs={"summary": "Mock execution completed"},
            artifacts=[],
            telemetry={"mock": True},
        )
        self.invoked_with: PathwayCallRequest | None = None

    @property
    def id(self) -> str:
        return "mock-runtime"

    @property
    def capabilities(self) -> list[str]:
        return []

    def invoke(self, request: PathwayCallRequest) -> PathwayResponse:
        self.invoked_with = request
        return self._response

    def resume(self, session_id: str, human_response: dict[str, Any]) -> PathwayResponse:
        return self._response


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


def test_execute_work_without_runtime_returns_simulated_result() -> None:
    plane = InMemoryOrganisationControlPlane()
    work = Work(id="w1", title="Simulated task", accountable_role_id="r1")
    plane.register_role(Role(id="r1", name="Operator"))
    plane.assign_work(work, Role(id="r1", name="Operator"))
    result = plane.execute_work("w1", {"input": "test"})
    assert result["status"] == "completed"
    assert result["outputs"]["simulated"] is True
    assert result["outputs"]["work_id"] == "w1"


def test_execute_work_with_runtime_delegates_to_runtime() -> None:
    mock_response = PathwayResponse(
        status=PathwayStatus.COMPLETED,
        outputs={"summary": "Runtime executed"},
        artifacts=["artifact1"],
        telemetry={"runtime": "mock"},
    )
    runtime = MockRuntime(response=mock_response)
    plane = InMemoryOrganisationControlPlane(runtime=runtime)
    work = Work(id="w1", title="Runtime task", accountable_role_id="r1")
    plane.register_role(Role(id="r1", name="Operator"))
    plane.assign_work(work, Role(id="r1", name="Operator"))
    result = plane.execute_work("w1", {"input": "test"})
    assert result["status"] == "completed"
    assert result["outputs"]["summary"] == "Runtime executed"
    assert result["artifacts"] == ["artifact1"]
    assert runtime.invoked_with is not None
    assert runtime.invoked_with.session_id == "ops-w1"


def test_execute_work_missing_work_returns_failure() -> None:
    plane = InMemoryOrganisationControlPlane()
    result = plane.execute_work("missing", {})
    assert result["status"] == "failed"
    assert "not found" in result["error"]
