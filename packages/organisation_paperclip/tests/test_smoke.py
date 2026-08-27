"""
End-to-end smoke test for the Paperclip-backed Organisation vertical slice.

Proves the complete chain:
  chat-style work request
  → Paperclip-backed OrganisationControlPlane
  → Paperclip Company/Agent/Issue
  → deterministic test agent execution
  → HeartbeatRun result
  → Organisation Work.outcome

Requires a running Paperclip instance on PAPERCLIP_URL.
"""

from __future__ import annotations

import os
import time

import pytest

from organisation_paperclip import PaperclipOrganisationControlPlane
from role import WorkStatus

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


def test_paperclip_end_to_end_smoke():
    plane = _make_plane(PAPERCLIP_COMPANY_ID)
    try:
        company = plane.create_company(f"smoke-company-{int(time.time())}")
        assert company is not None, "Failed to create Paperclip company"
        company_id = company["id"]

        test_plane = _make_plane(company_id)

        agent = test_plane.create_agent(
            name=f"smoke-agent-{int(time.time())}",
            adapter_type="process",
            capabilities=["test-capability"],
            adapter_config={
                "command": "echo",
                "args": ["{\"status\":\"success\",\"result\":\"smoke-test-success\"}"],
            },
        )
        assert agent is not None, "Failed to create test agent in Paperclip"

        work = test_plane.create_work(
            title="smoke-test-work",
            description="End-to-end smoke test work item",
            required_capability_ids=["test-capability"],
            assignee_agent_id=agent.id,
        )
        assert work is not None, "Failed to create work in Paperclip"
        assert work.status == WorkStatus.PENDING

        assignment = test_plane.assign_work(work, agent)
        assert assignment.assignee_id == agent.id
        assert work.assignee_agent_id == agent.id

        result = test_plane.trigger_execution(work.id, agent.id)
        assert result is not None, "Failed to trigger Paperclip execution"
        run_id = result["id"]

        work = test_plane.wait_for_execution(work.id, agent.id)
        assert work is not None, "Work not found after execution"
        assert work.status == WorkStatus.COMPLETED, f"Expected COMPLETED, got {work.status}"
        assert work.outcome is not None, "Work outcome is None"

        stdout = work.outcome.get("stdout", "") if isinstance(work.outcome, dict) else ""
        assert "smoke-test-success" in stdout, f"Expected success marker in stdout, got: {stdout}"

        run = test_plane.get_heartbeat_run(run_id)
        assert run is not None, "HeartbeatRun not found"
        assert run["status"] == "succeeded"

        retrieved = test_plane.get_work(work.id)
        assert retrieved is not None
        assert retrieved.status == WorkStatus.COMPLETED
        assert retrieved.outcome is not None

        test_plane.close()
    finally:
        plane.close()
