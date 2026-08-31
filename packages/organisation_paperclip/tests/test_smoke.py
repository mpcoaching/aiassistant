"""
End-to-end smoke test for the Paperclip-backed Organisation vertical slice.

Proves the complete event-driven flow:
  Organisation creates Work
  → Work is assigned
  → Organisation marks Work ready (emits READY event)
  → Operations receives READY event
  → Operations selects Paperclip backend
  → Paperclip adapter triggers execution
  → Paperclip completes
  → Operations reports result to Organisation
  → Organisation emits COMPLETED event
  → Work.outcome is available through organisational interface

Requires a running Paperclip instance on PAPERCLIP_URL.
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

from organisation_paperclip import PaperclipOrganisationControlPlane
from role import WorkStatus
from workflow_runner.src.operations import Operations, PaperclipBackend

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


def test_paperclip_event_driven_execution():
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

        events: list[Any] = []
        test_plane.on_event(events.append)

        paperclip_backend = PaperclipBackend(test_plane)
        Operations(
            org_plane=test_plane,
            backends=[paperclip_backend],
        )

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

        assigned_events = [e for e in events if e.event_type == "work.assigned"]
        assert len(assigned_events) == 1
        assert assigned_events[0].work_id == work.id

        ready_work = test_plane.mark_work_ready(work.id)
        assert ready_work is not None
        assert ready_work.status in (WorkStatus.READY, WorkStatus.COMPLETED)

        ready_events = [e for e in events if e.event_type == "work.ready"]
        assert len(ready_events) == 1
        assert ready_events[0].work_id == work.id

        time.sleep(2)

        completed_events = [e for e in events if e.event_type == "work.completed"]
        assert len(completed_events) >= 1, f"Expected completed event, got events: {[(e.event_type, e.work_id) for e in events]}"
        assert completed_events[0].work_id == work.id
        assert completed_events[0].outcome is not None

        retrieved = test_plane.get_work(work.id)
        assert retrieved is not None
        assert retrieved.status == WorkStatus.COMPLETED
        assert retrieved.outcome is not None

        stdout = retrieved.outcome.get("stdout", "") if isinstance(retrieved.outcome, dict) else ""
        assert "smoke-test-success" in stdout, f"Expected success marker in stdout, got: {stdout}"

        test_plane.close()
    finally:
        plane.close()
