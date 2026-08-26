"""
Minimal worker for the Organisation (Increment 21R).

Executes a work item and produces a tangible artifact.
This is the simplest real worker capable of demonstrating the end-to-end path:
  User → Chat → Assistant (inside Organisation) → Organisation Control Plane → Worker → result → Organisation Control Plane → Assistant → User

The worker is deliberately simple:
- No general-purpose agent runtime
- No planner
- No multi-agent framework
- No autonomous loop
- Just executes one concrete task and stores the result

Design constraints:
- Worker obtains work from OrganisationControlPlane
- Work lifecycle is managed by the Organisation
- Results are stored against the work item in the Organisation
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
    """Minimal worker that executes assigned work from the Organisation."""

    DEFAULT_AGENT_ID = "worker-agent"
    DEFAULT_AGENT_NAME = "Default Worker"

    def __init__(
        self,
        output_dir: str = "worker_outputs",
        agent_id: str = DEFAULT_AGENT_ID,
        capability_execution: CapabilityExecutionPort | None = None,
        capability_registry: Any | None = None,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._agent_id = agent_id
        self._capability_execution = capability_execution
        self._capability_registry = capability_registry

    def pickup(self, org_plane: Any) -> Work | None:
        """Pick up work assigned to this worker from the Organisation.

        Returns the first pending/assigned work item assigned to this worker's agent_id,
        or any unassigned work item if none is specifically assigned to this worker.
        """
        all_work = org_plane.list_work()
        for work in all_work:
            if work.status in (
                WorkStatus.PENDING,
                WorkStatus.ASSIGNED,
            ):
                if work.assignee_agent_id == self._agent_id or work.assignee_agent_id is None:
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
            if work.work_type == "capability_development":
                result = self._develop_capability(work, org_plane)
            elif work.required_capability_ids and self._capability_execution is not None:
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

    def _develop_capability(self, work: Work, org_plane: Any) -> dict[str, Any]:
        """Develop a new capability from a capability-gap work item.

        Produces a capability definition artifact, registers the capability
        in the organisational plane, and optionally in the capability registry.
        """
        from capability import Capability, CapabilityKind, CapabilityStatus

        capability_id = f"cap-{work.id}"
        capability_name = work.title.replace("Develop capability: ", "").strip()
        capability = Capability(
            id=capability_id,
            name=capability_name,
            description=work.description,
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.ACTIVE,
            owner=self._agent_id,
            created_by="worker",
            interface={
                "inputs": [{"name": "context", "type": "dict", "required": True}],
                "outputs": [{"name": "result", "type": "dict", "required": True}],
            },
        )

        org_plane.register_capability(capability)

        if self._capability_registry is not None:
            self._capability_registry.register(capability)

        artifact_path = self._write_capability_artifact(work.id, capability)

        return {
            "status": "completed",
            "execution_mode": "capability_development",
            "capability_id": capability_id,
            "capability_name": capability_name,
            "artifact_path": str(artifact_path),
            "work_id": work.id,
            "title": work.title,
            "description": work.description,
        }

    def _write_capability_artifact(
        self, work_id: str, capability: Any
    ) -> Path:
        """Write the capability development artifact to a file."""
        interface = capability.interface or {}
        if hasattr(interface, "inputs"):
            inputs = interface.inputs
            outputs = interface.outputs
        else:
            inputs = interface.get("inputs", [])
            outputs = interface.get("outputs", [])

        lines = [
            f"# Capability Development: {capability.name}",
            "",
            f"**Capability ID:** {capability.id}",
            f"**Kind:** {capability.capability_kind.value}",
            f"**Status:** {capability.status.value}",
            f"**Owner:** {capability.owner}",
            "",
            "## Purpose",
            capability.description or "No description provided.",
            "",
            "## Interface",
            "### Inputs",
        ]
        for inp in inputs:
            name = getattr(inp, "name", None)
            if name is None and hasattr(inp, "get"):
                name = inp.get("name", "?")
            if name is None:
                name = str(inp)
            type_ = getattr(inp, "type", None)
            if type_ is None and hasattr(inp, "get"):
                type_ = inp.get("type", "?")
            if type_ is None:
                type_ = "?"
            lines.append(f"- {name} ({type_})")
        lines.extend([
            "",
            "### Outputs",
        ])
        for out in outputs:
            name = getattr(out, "name", None)
            if name is None and hasattr(out, "get"):
                name = out.get("name", "?")
            if name is None:
                name = str(out)
            type_ = getattr(out, "type", None)
            if type_ is None and hasattr(out, "get"):
                type_ = out.get("type", "?")
            if type_ is None:
                type_ = "?"
            lines.append(f"- {name} ({type_})")
        lines.extend([
            "",
            "## Development Evidence",
            f"This capability was developed by {self._agent_id} in response to a capability gap.",
            f"Development work ID: {work_id}",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        content = "\n".join(lines)
        safe_name = capability.name.lower().replace(" ", "-")[:30]
        filename = f"{work_id}-{safe_name}.md"
        output_path = self._output_dir / filename
        output_path.write_text(content, encoding="utf-8")
        return output_path

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
            "This work item was processed by the minimal Organisation worker.",
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
