"""
Minimal worker for the enterprise plane (Increment 21R).

Executes a work item and produces a tangible artifact.
This is the simplest real worker capable of demonstrating the end-to-end path:
  User → Chat → Assistant → Enterprise Plane → Worker → result → Enterprise Plane → Assistant/User

The worker is deliberately simple:
- No general-purpose agent runtime
- No planner
- No multi-agent framework
- No autonomous loop
- Just executes one concrete task and stores the result

Design constraints:
- Worker obtains work from OrganisationControlPlane
- Work lifecycle is managed by the enterprise plane
- Results are stored against the work item in the enterprise plane
- Paperclip remains behind the OrganisationControlPlane boundary (future)
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from role import Agent, Work, WorkStatus


class Worker:
    """Minimal worker that executes assigned work from the enterprise plane."""

    DEFAULT_AGENT_ID = "worker-agent"
    DEFAULT_AGENT_NAME = "Default Worker"

    def __init__(self, output_dir: str = "worker_outputs", agent_id: str = DEFAULT_AGENT_ID) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._agent_id = agent_id

    def pickup(self, org_plane: Any) -> Work | None:
        """Pick up work assigned to this worker from the enterprise plane.

        Returns the first pending/assigned work item assigned to this worker's agent_id,
        or None if no work is available.
        """
        all_work = org_plane.list_work()
        for work in all_work:
            if work.assignee_agent_id == self._agent_id and work.status in (
                WorkStatus.PENDING,
                WorkStatus.ASSIGNED,
            ):
                return work
        return None

    def execute(self, work: Work, org_plane: Any) -> dict[str, Any]:
        """Execute a work item and store the result.

        Args:
            work: The work item to execute
            org_plane: The organisation control plane for state updates

        Returns:
            Result dict containing status, output_path, and summary
        """
        if work.assignee_agent_id is None:
            worker_agent = Agent(id=self._agent_id, name=self.DEFAULT_AGENT_NAME)
            org_plane.assign_work(work, worker_agent)

        work.status = WorkStatus.IN_PROGRESS
        work.updated_at = datetime.now(UTC)
        org_plane._work[work.id] = work

        try:
            result = self._do_work(work)
            work.status = WorkStatus.COMPLETED
            work.outcome = result
            work.updated_at = datetime.now(UTC)
            org_plane._work[work.id] = work
            return result
        except Exception as exc:
            work.status = WorkStatus.FAILED
            work.outcome = {
                "status": "failed",
                "error": str(exc),
                "summary": f"Worker failed: {exc}",
            }
            work.updated_at = datetime.now(UTC)
            org_plane._work[work.id] = work
            return work.outcome

    def _do_work(self, work: Work) -> dict[str, Any]:
        """Perform the actual work.

        For this increment, the worker creates a simple markdown summary document.
        This is the smallest real task that produces a tangible, inspectable artifact.

        Future increments can replace this with:
        - Capability execution via CapabilityExecutionPort
        - Paperclip agent dispatch
        - More sophisticated task handling
        """
        summary = self._generate_summary(work)
        output_path = self._write_output(work.id, work.title, summary)

        return {
            "status": "completed",
            "summary": summary,
            "output_path": str(output_path),
            "output_type": "markdown",
            "work_id": work.id,
            "title": work.title,
            "description": work.description,
        }

    def _generate_summary(self, work: Work) -> str:
        """Generate a simple human-readable summary of the work."""
        lines = [
            f"# Work Summary: {work.title}",
            "",
            f"**Work ID:** {work.id}",
            f"**Type:** {work.work_type}",
            f"**Priority:** {work.priority}",
            f"**Status:** {work.status.value}",
            "",
            "## Description",
            work.description or "No description provided.",
            "",
            "## Result",
            "This work item was processed by the minimal enterprise-plane worker.",
            f"The result has been written to `worker_outputs/{work.id}.md`.",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ]
        return "\n".join(lines)

    def _write_output(self, work_id: str, title: str, content: str) -> Path:
        """Write the work output to a file."""
        safe_title = title.lower().replace(" ", "-")[:30]
        filename = f"{work_id}-{safe_title}.md"
        output_path = self._output_dir / filename
        output_path.write_text(content, encoding="utf-8")
        return output_path
