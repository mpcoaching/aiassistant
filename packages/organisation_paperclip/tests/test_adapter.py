"""Tests for PaperclipOrganisationControlPlane adapter."""

from __future__ import annotations

from typing import Any

import respx
from httpx import Response
from role import Agent, AssignmentStatus, RoleStatus, Work, WorkStatus

from organisation_paperclip import PaperclipAdapterError, PaperclipOrganisationControlPlane


def _make_plane(api_key: str = "test-key", company_id: str = "test-org", **kwargs: Any) -> PaperclipOrganisationControlPlane:
    return PaperclipOrganisationControlPlane(
        base_url="http://localhost:3100",
        api_key=api_key,
        company_id=company_id,
        **kwargs,
    )


def test_get_role_returns_mapped_role():
    with respx.mock:
        respx.get("http://localhost:3100/api/agents/agent-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "agent-1",
                    "name": "Researcher",
                    "title": "Research Agent",
                    "status": "idle",
                    "capabilities": ["research", "writing"],
                    "reportsTo": "ceo-1",
                    "metadata": {},
                },
            )
        )
        plane = _make_plane()
        role = plane.get_role("agent-1")
        assert role is not None
        assert role.id == "agent-1"
        assert role.name == "Researcher"
        assert role.status == RoleStatus.ACTIVE
        assert "research" in role.required_capability_ids
        plane.close()


def test_list_roles_returns_active_agents():
    with respx.mock:
        respx.get("http://localhost:3100/api/companies/test-org/agents").mock(
            return_value=Response(
                200,
                json=[
                    {"id": "agent-1", "name": "Researcher", "status": "idle", "capabilities": ["research"], "reportsTo": None, "metadata": {}},
                    {"id": "agent-2", "name": "Writer", "status": "active", "capabilities": ["writing"], "reportsTo": "agent-1", "metadata": {}},
                    {"id": "agent-3", "name": "Inactive", "status": "paused", "capabilities": [], "reportsTo": None, "metadata": {}},
                ],
            )
        )
        plane = _make_plane()
        roles = plane.list_roles()
        assert len(roles) == 2
        assert {r.id for r in roles} == {"agent-1", "agent-2"}
        plane.close()


def test_create_and_assign_work():
    with respx.mock:
        respx.post("http://localhost:3100/api/companies/test-org/issues").mock(
            return_value=Response(
                201,
                json={
                    "id": "issue-1",
                    "title": "Test task",
                    "description": "A test task",
                    "status": "todo",
                    "priority": "medium",
                    "assigneeAgentId": None,
                    "capabilities": ["research"],
                    "createdAt": "2026-08-26T00:00:00Z",
                    "updatedAt": "2026-08-26T00:00:00Z",
                },
            )
        )
        respx.patch("http://localhost:3100/api/issues/issue-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "issue-1",
                    "title": "Test task",
                    "status": "in_progress",
                    "assigneeAgentId": "agent-1",
                },
            )
        )
        plane = _make_plane()
        work = Work(
            id="issue-1",
            title="Test task",
            description="A test task",
            work_type="task",
            status=WorkStatus.PENDING,
            priority="medium",
            accountable_role_id="unassigned",
            required_capability_ids=["research"],
            organisation_id="test-org",
        )
        assignee = Agent(id="agent-1", name="Researcher", role_type="agent", status=RoleStatus.ACTIVE)
        assignment = plane.assign_work(work, assignee)
        assert assignment.assignee_id == "agent-1"
        assert assignment.assignee_type == "agent"
        assert assignment.status == AssignmentStatus.ACCEPTED
        assert work.status == WorkStatus.ASSIGNED
        assert work.assignee_agent_id == "agent-1"
        plane.close()


def test_get_work_returns_mapped_work():
    with respx.mock:
        respx.get("http://localhost:3100/api/issues/issue-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "issue-1",
                    "title": "Research task",
                    "description": "Do research",
                    "status": "in_progress",
                    "priority": "high",
                    "assigneeAgentId": "agent-1",
                    "capabilities": ["research"],
                    "createdAt": "2026-08-26T00:00:00Z",
                    "updatedAt": "2026-08-26T01:00:00Z",
                },
            )
        )
        plane = _make_plane()
        work = plane.get_work("issue-1")
        assert work is not None
        assert work.id == "issue-1"
        assert work.title == "Research task"
        assert work.status == WorkStatus.IN_PROGRESS
        assert work.assignee_agent_id == "agent-1"
        plane.close()


def test_list_work_returns_mapped_issues():
    with respx.mock:
        respx.get("http://localhost:3100/api/companies/test-org/issues").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": "issue-1",
                        "title": "Task 1",
                        "status": "todo",
                        "priority": "medium",
                        "assigneeAgentId": None,
                        "capabilities": ["research"],
                        "createdAt": "2026-08-26T00:00:00Z",
                        "updatedAt": "2026-08-26T00:00:00Z",
                    },
                    {
                        "id": "issue-2",
                        "title": "Task 2",
                        "status": "done",
                        "priority": "low",
                        "assigneeAgentId": "agent-1",
                        "capabilities": ["writing"],
                        "createdAt": "2026-08-26T00:00:00Z",
                        "updatedAt": "2026-08-26T00:00:00Z",
                    },
                ],
            )
        )
        plane = _make_plane()
        works = plane.list_work()
        assert len(works) == 2
        assert works[0].status == WorkStatus.PENDING
        assert works[1].status == WorkStatus.COMPLETED
        plane.close()


def test_mark_work_ready_transitions_to_in_progress():
    with respx.mock:
        respx.get("http://localhost:3100/api/issues/issue-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "issue-1",
                    "title": "Task",
                    "status": "todo",
                    "priority": "medium",
                    "assigneeAgentId": None,
                    "capabilities": ["research"],
                    "createdAt": "2026-08-26T00:00:00Z",
                    "updatedAt": "2026-08-26T00:00:00Z",
                },
            )
        )
        respx.patch("http://localhost:3100/api/issues/issue-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "issue-1",
                    "title": "Task",
                    "status": "in_progress",
                    "assigneeAgentId": None,
                },
            )
        )
        plane = _make_plane()
        work = plane.get_work("issue-1")
        assert work is not None
        result = plane.mark_work_ready("issue-1")
        assert result is not None
        assert result.status == WorkStatus.IN_PROGRESS
        plane.close()


def test_query_capability_returns_availability():
    with respx.mock:
        respx.get("http://localhost:3100/api/companies/test-org/agents").mock(
            return_value=Response(
                200,
                json=[
                    {"id": "agent-1", "name": "Researcher", "status": "idle", "capabilities": ["research"], "reportsTo": None, "metadata": {}},
                ],
            )
        )
        plane = _make_plane()
        available = plane.query_capability("research")
        assert available is not None
        assert available["capability_id"] == "research"
        assert available["available"] is True
        plane.close()


def test_query_capability_returns_none_when_missing():
    with respx.mock:
        respx.get("http://localhost:3100/api/companies/test-org/agents").mock(
            return_value=Response(
                200,
                json=[
                    {"id": "agent-1", "name": "Researcher", "status": "idle", "capabilities": ["research"], "reportsTo": None, "metadata": {}},
                ],
            )
        )
        plane = _make_plane()
        missing = plane.query_capability("nonexistent")
        assert missing is None
        plane.close()


def test_api_error_raises_adapter_error():
    with respx.mock:
        respx.get("http://localhost:3100/api/companies/test-org/agents").mock(
            return_value=Response(500, json={"error": "internal"})
        )
        plane = _make_plane()
        with respx.mock:
            try:
                plane.list_roles()
            except PaperclipAdapterError:
                pass
        plane.close()


def test_adapter_preserves_organisation_id():
    with respx.mock:
        respx.get("http://localhost:3100/api/companies/my-org/agents").mock(
            return_value=Response(200, json=[])
        )
        plane = PaperclipOrganisationControlPlane(
            base_url="http://localhost:3100",
            api_key="test-key",
            company_id="my-org",
        )
        assert plane._company_id == "my-org"
        plane.list_roles()
        plane.close()


def test_create_work_posts_issue():
    with respx.mock:
        respx.post("http://localhost:3100/api/companies/test-org/issues").mock(
            return_value=Response(
                201,
                json={
                    "id": "issue-new",
                    "title": "New task",
                    "description": "Description",
                    "status": "todo",
                    "priority": "high",
                    "assigneeAgentId": None,
                    "capabilities": ["research"],
                    "createdAt": "2026-08-26T00:00:00Z",
                    "updatedAt": "2026-08-26T00:00:00Z",
                },
            )
        )
        plane = _make_plane()
        work = plane.create_work(
            title="New task",
            description="Description",
            required_capability_ids=["research"],
            priority="high",
        )
        assert work.id == "issue-new"
        assert work.status == WorkStatus.PENDING
        assert work.required_capability_ids == ["research"]
        plane.close()


def test_create_agent_returns_mapped_role():
    with respx.mock:
        respx.post("http://localhost:3100/api/companies/test-org/agents").mock(
            return_value=Response(
                201,
                json={
                    "id": "agent-new",
                    "name": "NewAgent",
                    "title": "New Agent",
                    "status": "idle",
                    "capabilities": ["research"],
                    "reportsTo": None,
                    "metadata": {},
                },
            )
        )
        plane = _make_plane()
        role = plane.create_agent(name="NewAgent", adapter_type="process", capabilities=["research"])
        assert role is not None
        assert role.id == "agent-new"
        assert role.name == "NewAgent"
        plane.close()


def test_trigger_execution_returns_run_summary():
    with respx.mock:
        respx.post("http://localhost:3100/api/agents/agent-1/heartbeat/invoke").mock(
            return_value=Response(
                200,
                json={
                    "id": "run-1",
                    "agentId": "agent-1",
                    "status": "queued",
                    "invocationSource": "on_demand",
                    "triggerDetail": "manual",
                },
            )
        )
        plane = _make_plane()
        result = plane.trigger_execution("issue-1", "agent-1")
        assert result is not None
        assert result["id"] == "run-1"
        plane.close()


def test_wait_for_execution_completes():
    with respx.mock:
        respx.get("http://localhost:3100/api/issues/issue-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "issue-1",
                    "title": "Task",
                    "status": "todo",
                    "priority": "medium",
                    "assigneeAgentId": None,
                    "capabilities": ["research"],
                    "createdAt": "2026-08-26T00:00:00Z",
                    "updatedAt": "2026-08-26T00:00:00Z",
                },
            )
        )
        respx.get("http://localhost:3100/api/companies/test-org/heartbeat-runs").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": "run-1",
                        "companyId": "test-org",
                        "agentId": "agent-1",
                        "status": "completed",
                        "invocationSource": "on_demand",
                        "contextSnapshot": {"issueId": "issue-1"},
                        "resultJson": {"output": "done"},
                        "startedAt": "2026-08-26T00:00:00Z",
                        "finishedAt": "2026-08-26T00:01:00Z",
                    }
                ],
            )
        )
        respx.get("http://localhost:3100/api/heartbeat-runs/run-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "run-1",
                    "companyId": "test-org",
                    "agentId": "agent-1",
                    "status": "completed",
                    "invocationSource": "on_demand",
                    "contextSnapshot": {"issueId": "issue-1"},
                    "resultJson": {"output": "done"},
                    "startedAt": "2026-08-26T00:00:00Z",
                    "finishedAt": "2026-08-26T00:01:00Z",
                },
            )
        )
        plane = _make_plane(poll_interval=0.1, max_poll_attempts=3)
        work = plane.wait_for_execution("issue-1", "agent-1")
        assert work is not None
        assert work.status == WorkStatus.COMPLETED
        assert work.outcome == {"output": "done"}
        plane.close()


def test_wait_for_execution_failure():
    with respx.mock:
        respx.get("http://localhost:3100/api/issues/issue-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "issue-1",
                    "title": "Task",
                    "status": "todo",
                    "priority": "medium",
                    "assigneeAgentId": None,
                    "capabilities": ["research"],
                    "createdAt": "2026-08-26T00:00:00Z",
                    "updatedAt": "2026-08-26T00:00:00Z",
                },
            )
        )
        respx.get("http://localhost:3100/api/companies/test-org/heartbeat-runs").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": "run-1",
                        "companyId": "test-org",
                        "agentId": "agent-1",
                        "status": "failed",
                        "invocationSource": "on_demand",
                        "contextSnapshot": {"issueId": "issue-1"},
                        "resultJson": {"error": "adapter not found"},
                        "startedAt": "2026-08-26T00:00:00Z",
                        "finishedAt": "2026-08-26T00:01:00Z",
                    }
                ],
            )
        )
        respx.get("http://localhost:3100/api/heartbeat-runs/run-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "run-1",
                    "companyId": "test-org",
                    "agentId": "agent-1",
                    "status": "failed",
                    "invocationSource": "on_demand",
                    "contextSnapshot": {"issueId": "issue-1"},
                    "resultJson": {"error": "adapter not found"},
                    "startedAt": "2026-08-26T00:00:00Z",
                    "finishedAt": "2026-08-26T00:01:00Z",
                },
            )
        )
        plane = _make_plane(poll_interval=0.1, max_poll_attempts=3)
        work = plane.wait_for_execution("issue-1", "agent-1")
        assert work is not None
        assert work.status == WorkStatus.FAILED
        assert work.outcome == {"error": "adapter not found"}
        plane.close()


def test_get_heartbeat_run():
    with respx.mock:
        respx.get("http://localhost:3100/api/heartbeat-runs/run-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "run-1",
                    "agentId": "agent-1",
                    "status": "completed",
                    "resultJson": {"output": "done"},
                },
            )
        )
        plane = _make_plane()
        run = plane.get_heartbeat_run("run-1")
        assert run is not None
        assert run["id"] == "run-1"
        assert run["status"] == "completed"
        plane.close()


def test_get_heartbeat_runs_for_issue():
    with respx.mock:
        respx.get("http://localhost:3100/api/companies/test-org/heartbeat-runs").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": "run-1",
                        "companyId": "test-org",
                        "agentId": "agent-1",
                        "status": "completed",
                        "contextSnapshot": {"issueId": "issue-1"},
                    },
                    {
                        "id": "run-2",
                        "companyId": "test-org",
                        "agentId": "agent-1",
                        "status": "queued",
                        "contextSnapshot": {"issueId": "issue-2"},
                    },
                ],
            )
        )
        respx.get("http://localhost:3100/api/heartbeat-runs/run-1").mock(
            return_value=Response(
                200,
                json={
                    "id": "run-1",
                    "companyId": "test-org",
                    "agentId": "agent-1",
                    "status": "completed",
                    "contextSnapshot": {"issueId": "issue-1"},
                    "resultJson": {"output": "done"},
                },
            )
        )
        respx.get("http://localhost:3100/api/heartbeat-runs/run-2").mock(
            return_value=Response(
                200,
                json={
                    "id": "run-2",
                    "companyId": "test-org",
                    "agentId": "agent-1",
                    "status": "queued",
                    "contextSnapshot": {"issueId": "issue-2"},
                },
            )
        )
        plane = _make_plane()
        runs = plane.get_heartbeat_runs_for_issue("issue-1")
        assert len(runs) == 1
        assert runs[0]["id"] == "run-1"
        plane.close()


def test_on_event_handler_called():
    with respx.mock:
        respx.get("http://localhost:3100/api/companies/test-org/agents").mock(
            return_value=Response(200, json=[])
        )
        plane = _make_plane()
        events: list[Any] = []

        def handler(event: Any) -> None:
            events.append(event)

        plane.on_event(handler)
        plane.emit_event({"type": "test"})
        assert len(events) == 1
        plane.close()


def test_on_signal_handler_called():
    with respx.mock:
        respx.get("http://localhost:3100/api/companies/test-org/agents").mock(
            return_value=Response(200, json=[])
        )
        plane = _make_plane()
        signals: list[Any] = []

        def handler(signal: Any) -> None:
            signals.append(signal)

        plane.on_signal(handler)
        plane.emit_signal({"type": "capacity.pressure"})
        assert len(signals) == 1
        plane.close()
