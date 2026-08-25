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
from contracts.capability_execution import CapabilityExecutionPort, ExecutionResult


class Worker:
    """Minimal worker that executes assigned work from the enterprise plane."""

    DEFAULT_AGENT_ID = "worker-agent"
    DEFAULT_AGENT_NAME = "Default Worker"

    def __init__(
        self,
        output_dir: str = "worker_outputs",
        agent_id: str = DEFAULT_AGENT_ID,
        capability_execution: CapabilityExecutionPort | None = None,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._agent_id = agent_id
        self._capability_execution = capability_execution

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
            if work.required_capability_ids and self._capability_execution is not None:
                result = self._execute_capability(work)
            else:
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

    def _execute_capability(self, work: Work) -> dict[str, Any]:
        """Execute the capability referenced by the work item.

        Invokes CapabilityExecutionPort with the first required_capability_id
        and stores the real ExecutionResult.
        """
        capability_id = work.required_capability_ids[0]
        actor_context = {
            "actor_id": self._agent_id,
            "actor_type": "agent",
        }
        execution_result: ExecutionResult = self._capability_execution.execute(
            capability_id=capability_id,
            context=work.context or {},
            actor_context=actor_context,
        )
        result = {
            "status": "completed",
            "execution_mode": "capability_execution_port",
            "capability_id": capability_id,
            "outputs": dict(execution_result.outputs),
            "artifacts": list(execution_result.artifacts),
            "telemetry": dict(execution_result.telemetry),
            "work_id": work.id,
            "title": work.title,
            "description": work.description,
        }
        return result

    def _do_work(self, work: Work) -> dict[str, Any]:
        """Perform the actual work.

        Fallback when no capability is specified. Creates a simple markdown
        summary document as a tangible artifact.
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
