"""
Integration tests for Paperclip-backed Organisation vertical slice.

These tests require a running Paperclip instance. They are excluded from the
normal test suite by the ``integration`` marker.

Environment variables:
    PAPERCLIP_URL       Base URL for Paperclip (default: http://localhost:3100)
    PAPERCLIP_API_KEY   Bearer token for Paperclip API (optional for local_trusted)
    PAPERCLIP_COMPANY_ID Company ID to use (default: default)

Run:
    PAPERCLIP_API_KEY=<key> python -m pytest \
        packages/organisation_paperclip/tests/test_integration.py -v
"""

from __future__ import annotations

import os
import time

import pytest
from role import Agent, WorkStatus

from organisation_paperclip import PaperclipOrganisationControlPlane

PAPERCLIP_URL = os.getenv("PAPERCLIP_URL", "http://localhost:3100")
PAPERCLIP_API_KEY = os.getenv("PAPERCLIP_API_KEY", "")
PAPERCLIP_COMPANY_ID = os.getenv("PAPERCLIP_COMPANY_ID", "default")

pytestmark = pytest.mark.integration


def _make_plane(company_id: str) -> PaperclipOrganisationControlPlane:
    return PaperclipOrganisationControlPlane(
        base_url=PAPERCLIP_URL,
        api_key=PAPERCLIP_API_KEY,
        company_id=company_id,
    )


@pytest.fixture
def test_company() -> dict:
    plane = _make_plane(PAPERCLIP_COMPANY_ID)
    try:
        company = plane.create_company(f"test-company-{int(time.time())}")
        assert company is not None, "Failed to create test company in Paperclip"
        yield company
    finally:
        plane.close()


@pytest.fixture
def plane(test_company: dict) -> PaperclipOrganisationControlPlane:
    p = _make_plane(test_company["id"])
    yield p
    p.close()


@pytest.fixture
def test_agent(plane: PaperclipOrganisationControlPlane) -> Agent:
    agent = plane.create_agent(
        name=f"test-agent-{int(time.time())}",
        adapter_type="process",
        capabilities=["test-capability"],
        adapter_config={
            "command": "echo",
            "args": ["{\"status\":\"success\",\"result\":\"integration-test-success\"}"],
        },
    )
    assert agent is not None, "Failed to create deterministic test agent in Paperclip"
    return agent


@pytest.fixture
def failure_agent(plane: PaperclipOrganisationControlPlane) -> Agent:
    agent = plane.create_agent(
        name=f"test-agent-fail-{int(time.time())}",
        adapter_type="process",
        capabilities=["test-capability-fail"],
        adapter_config={
            "command": "false",
        },
    )
    assert agent is not None, "Failed to create failure test agent in Paperclip"
    return agent


class TestPaperclipVerticalSlice:
    """Prove the real Paperclip-backed Organisation vertical slice."""

    def test_organisation_creates_work_in_paperclip(self, plane: PaperclipOrganisationControlPlane):
        work = plane.create_work(
            title="vertical-slice-test",
            description="Prove work creation in Paperclip",
            required_capability_ids=["test"],
        )
        assert work is not None
        assert work.id != ""
        assert work.status == WorkStatus.PENDING

        retrieved = plane.get_work(work.id)
        assert retrieved is not None
        assert retrieved.title == "vertical-slice-test"

    def test_work_is_assigned_to_agent(self, plane: PaperclipOrganisationControlPlane, test_agent: Agent):
        work = plane.create_work(
            title="assign-test",
            description="Prove assignment",
            required_capability_ids=["test-capability"],
        )
        assignment = plane.assign_work(work, test_agent)
        assert assignment.assignee_id == test_agent.id
        assert work.status == WorkStatus.ASSIGNED
        assert work.assignee_agent_id == test_agent.id

    def test_paperclip_heartbeat_run_is_created(self, plane: PaperclipOrganisationControlPlane, test_agent: Agent):
        work = plane.create_work(
            title="heartbeat-test",
            description="Prove heartbeat run creation",
            required_capability_ids=["test-capability"],
            assignee_agent_id=test_agent.id,
        )
        result = plane.trigger_execution(work.id, test_agent.id)
        assert result is not None
        assert "id" in result

    def test_organisation_observes_execution_result(self, plane: PaperclipOrganisationControlPlane, test_agent: Agent):
        work = plane.create_work(
            title="observe-result-test",
            description="Prove result observation",
            required_capability_ids=["test-capability"],
            assignee_agent_id=test_agent.id,
        )
        plane.trigger_execution(work.id, test_agent.id)
        work = plane.wait_for_execution(work.id, test_agent.id)
        assert work is not None
        assert work.status == WorkStatus.COMPLETED
        assert work.outcome is not None
        stdout = work.outcome.get("stdout", "") if isinstance(work.outcome, dict) else ""
        assert "integration-test-success" in stdout

    def test_failure_path_propagates_to_organisation(self, plane: PaperclipOrganisationControlPlane, failure_agent: Agent):
        work = plane.create_work(
            title="failure-test",
            description="Prove failure propagation",
            required_capability_ids=["test-capability-fail"],
            assignee_agent_id=failure_agent.id,
        )
        plane.trigger_execution(work.id, failure_agent.id)
        work = plane.wait_for_execution(work.id, failure_agent.id)
        assert work is not None
        assert work.status == WorkStatus.FAILED
        assert work.outcome is not None

    def test_result_available_without_paperclip_knowledge(self, plane: PaperclipOrganisationControlPlane, test_agent: Agent):
        work = plane.create_work(
            title="domain-result-test",
            description="Prove domain representation",
            required_capability_ids=["test-capability"],
            assignee_agent_id=test_agent.id,
        )
        plane.trigger_execution(work.id, test_agent.id)
        work = plane.wait_for_execution(work.id, test_agent.id)
        assert work is not None
        result_dict = work.model_dump()
        assert "outcome" in result_dict
        assert "status" in result_dict
        assert result_dict["status"] == WorkStatus.COMPLETED.value
