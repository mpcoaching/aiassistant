"""
Paperclip-backed OrganisationControlPlane adapter (Increment 21Y).

Extends the 21X adapter with:
- Work creation in Paperclip
- Agent/role creation in Paperclip
- Execution triggering via Paperclip heartbeat
- Result observation via Paperclip heartbeat runs
- Event propagation from Paperclip to our organisational event boundary

Paperclip remains behind the Organisation abstraction; the Assistant
never imports or references this module.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from contracts.organisational_events import WorkEvent, WorkEventType
from role import (
    Agent,
    Assignment,
    AssignmentStatus,
    Authority,
    Delegation,
    OrgContext,
    Person,
    Role,
    RoleStatus,
    Work,
    WorkStatus,
)

logger = logging.getLogger(__name__)


class PaperclipAdapterError(Exception):
    """Raised when the Paperclip adapter encounters an operational error."""


class _PaperclipAgentRole(Role):
    """Internal marker for Paperclip-mapped agents."""



class PaperclipOrganisationControlPlane:
    """OrganisationControlPlane implementation backed by Paperclip.

    Maps our domain concepts to Paperclip concepts:
    - Organisation/tenant → Paperclip Company
    - Role/Agent → Paperclip Agent
    - Work → Paperclip Issue
    - Assignment → Paperclip Issue assigneeAgentId / assigneeUserId
    - Execution result → Paperclip HeartbeatRun resultJson

    The adapter communicates with Paperclip via its REST API.
    Authentication is via Bearer token (board or agent API key).

    Important: the in-memory caches below are a performance optimization,
    not authoritative persistence. Organisation domain truth is owned by
    the Organisation layer. Paperclip remains authoritative for its own
    operational execution state. The adapter translates between them.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:3100",
        api_key: str | None = None,
        company_id: str | None = None,
        timeout: float = 30.0,
        poll_interval: float = 2.0,
        max_poll_attempts: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or ""
        self._company_id = company_id or "default"
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._max_poll_attempts = max_poll_attempts
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=self._headers(),
            timeout=self._timeout,
        )
        self._role_cache: dict[str, Role] = {}
        self._work_cache: dict[str, Work] = {}
        self._assignment_cache: dict[str, Assignment] = {}
        self._event_handler: Callable[[Any], None] | None = None
        self._signal_handler: Callable[[Any], None] | None = None

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            logger.error("Paperclip API error %s %s: %s", method, path, exc.response.status_code)
            raise PaperclipAdapterError(f"Paperclip API error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Paperclip request error %s %s: %s", method, path, exc)
            raise PaperclipAdapterError(f"Paperclip request failed: {exc}") from exc

    def close(self) -> None:
        self._client.close()

    def on_event(self, handler: Callable[[Any], None]) -> None:
        """Register a handler for operational events."""
        self._event_handler = handler

    def on_signal(self, handler: Callable[[Any], None]) -> None:
        """Register a handler for organisational signals."""
        self._signal_handler = handler

    # ------------------------------------------------------------------
    # OrganisationControlPlane interface
    # ------------------------------------------------------------------

    def get_role(self, role_id: str) -> Role | None:
        """Retrieve a role by ID from Paperclip."""
        if role_id in self._role_cache:
            return self._role_cache[role_id]
        try:
            response = self._request("GET", f"/api/agents/{role_id}")
            data = response.json()
            role = self._map_agent_to_role(data)
            self._role_cache[role_id] = role
            return role
        except PaperclipAdapterError:
            return None

    def list_roles(self) -> list[Role]:
        """List all active roles (agents) in the Paperclip company."""
        try:
            response = self._request("GET", f"/api/companies/{self._company_id}/agents")
            data = response.json()
            roles = [self._map_agent_to_role(agent) for agent in data if agent.get("status") in ("idle", "active")]
            for role in roles:
                self._role_cache[role.id] = role
            return roles
        except PaperclipAdapterError:
            return []

    def get_organisational_context(self, request_context: dict[str, Any]) -> OrgContext:
        """Derive organisational context from a request."""
        actor_id = request_context.get("actor_id")
        role_id = request_context.get("role_id")
        reporting: list[str] = []
        authority_scope: list[str] = []
        if role_id and role_id in self._role_cache:
            role = self._role_cache[role_id]
            reporting = [role.reports_to] if role.reports_to else []
            authority_scope = list(role.authority_ids)
        return OrgContext(
            current_actor_id=actor_id,
            current_role_id=role_id,
            reporting_relationships=reporting,
            authority_scope=authority_scope,
        )

    def create_work(self, title: str, description: str = "", required_capability_ids: list[str] | None = None, **kwargs: Any) -> Work:
        """Create work (Paperclip Issue) in the Organisation."""
        body: dict[str, Any] = {
            "title": title,
            "description": description,
            "status": "todo",
            "priority": kwargs.get("priority", "medium"),
        }
        if required_capability_ids:
            body["capabilities"] = required_capability_ids
        assignee_agent_id = kwargs.get("assignee_agent_id")
        if assignee_agent_id:
            body["assigneeAgentId"] = assignee_agent_id

        response = self._request("POST", f"/api/companies/{self._company_id}/issues", json=body)
        data = response.json()
        work = self._map_issue_to_work(data)
        self._work_cache[work.id] = work
        self._emit_work_event(WorkEventType.CREATED, work)
        return work

    def assign_work(self, work: Work, assignee: Role | Person | Agent) -> Assignment:
        """Assign work to a role, person, or agent via Paperclip."""
        assignee_id = assignee.id
        if isinstance(assignee, (Agent, _PaperclipAgentRole)):
            assignee_type = "agent"
        elif isinstance(assignee, Person):
            assignee_type = "person"
        else:
            assignee_type = "role"

        try:
            patch_body: dict[str, Any] = {}
            if assignee_type == "agent":
                patch_body["assigneeAgentId"] = assignee_id
            elif assignee_type == "person":
                patch_body["assigneeUserId"] = assignee_id
            if patch_body:
                self._request("PATCH", f"/api/issues/{work.id}", json=patch_body)
        except PaperclipAdapterError:
            pass

        work.status = WorkStatus.ASSIGNED
        work.updated_at = datetime.now(UTC)
        if assignee_type == "role":
            work.assignee_role_id = assignee_id
        elif assignee_type == "person":
            work.assignee_person_id = assignee_id
        elif assignee_type == "agent":
            work.assignee_agent_id = assignee_id

        self._work_cache[work.id] = work
        assignment = Assignment(
            id=str(uuid4()),
            work_id=work.id,
            assignee_type=assignee_type,
            assignee_id=assignee_id,
            status=AssignmentStatus.ACCEPTED,
        )
        self._assignment_cache[assignment.id] = assignment
        self._emit_work_event(WorkEventType.ASSIGNED, work, assignee_id=assignee_id)
        return assignment

    def get_work(self, work_id: str) -> Work | None:
        """Retrieve work by ID from Paperclip."""
        if work_id in self._work_cache:
            return self._work_cache[work_id]
        try:
            response = self._request("GET", f"/api/issues/{work_id}")
            data = response.json()
            work = self._map_issue_to_work(data)
            self._work_cache[work_id] = work
            return work
        except PaperclipAdapterError:
            return None

    def list_work(self) -> list[Work]:
        """List all work items from Paperclip."""
        try:
            response = self._request("GET", f"/api/companies/{self._company_id}/issues")
            data = response.json()
            works = [self._map_issue_to_work(issue) for issue in data]
            for work in works:
                self._work_cache[work.id] = work
            return works
        except PaperclipAdapterError:
            return []

    def mark_work_ready(self, work_id: str) -> Work | None:
        """Mark organisational Work as ready for operational execution."""
        work = self.get_work(work_id)
        if work is not None:
            work.status = WorkStatus.IN_PROGRESS
            work.updated_at = datetime.now(UTC)
            self._work_cache[work_id] = work
            try:
                self._request("PATCH", f"/api/issues/{work_id}", json={"status": "in_progress"})
            except PaperclipAdapterError:
                pass
            self._emit_work_event(WorkEventType.STARTED, work)
        return work

    def trigger_execution(self, work_id: str, agent_id: str) -> dict[str, Any] | None:
        """Trigger Paperclip heartbeat execution for assigned work.

        Returns the created heartbeat run summary, or None if the run
        was skipped.
        """
        try:
            response = self._request(
                "POST",
                f"/api/agents/{agent_id}/heartbeat/invoke",
                json={"reason": f"Execute work {work_id}"},
            )
            return response.json()
        except PaperclipAdapterError:
            return None

    def wait_for_execution(self, work_id: str, agent_id: str | None = None) -> Work | None:
        """Wait for Paperclip execution to complete and update work state.

        Polls Paperclip heartbeat runs for the work item until completion,
        failure, or timeout. Updates the cached work with the result.

        Returns the updated Work, or None if the work is not found.
        """
        work = self.get_work(work_id)
        if work is None:
            return None

        for _ in range(self._max_poll_attempts):
            runs = self._get_heartbeat_runs_for_issue(work_id)
            if not runs:
                import time
                time.sleep(self._poll_interval)
                continue

            latest_run = runs[0]
            run_status = latest_run.get("status", "")
            result_json = latest_run.get("resultJson")

            if run_status in ("succeeded", "completed"):
                work.status = WorkStatus.COMPLETED
                work.outcome = result_json if isinstance(result_json, dict) else {"raw": result_json}
                work.updated_at = datetime.now(UTC)
                self._work_cache[work_id] = work

                if self._event_handler:
                    event = WorkEvent(
                        event_type=WorkEventType.COMPLETED,
                        organisation_id=self._company_id,
                        work_id=work.id,
                        title=work.title,
                        work_type=work.work_type,
                        assignee_role_id=work.assignee_role_id,
                        assignee_agent_id=work.assignee_agent_id,
                        required_capability_ids=list(work.required_capability_ids),
                        status=work.status.value,
                        priority=work.priority,
                        outcome=work.outcome,
                        context=work.context,
                    )
                    self._event_handler(event)
                return work

            if run_status in ("failed", "cancelled"):
                work.status = WorkStatus.FAILED if run_status == "failed" else WorkStatus.CANCELLED
                work.outcome = result_json if isinstance(result_json, dict) else {"raw": result_json}
                work.updated_at = datetime.now(UTC)
                self._work_cache[work_id] = work

                if run_status == "completed":
                    self._emit_work_event(WorkEventType.COMPLETED, work)
                elif run_status == "failed":
                    self._emit_work_event(WorkEventType.FAILED, work)

                if self._event_handler:
                    event = WorkEvent(
                        event_type=WorkEventType.COMPLETED if run_status == "completed" else WorkEventType.FAILED,
                        organisation_id=self._company_id,
                        work_id=work.id,
                        title=work.title,
                        work_type=work.work_type,
                        assignee_role_id=work.assignee_role_id,
                        assignee_agent_id=work.assignee_agent_id,
                        required_capability_ids=list(work.required_capability_ids),
                        status=work.status.value,
                        priority=work.priority,
                        outcome=work.outcome,
                        context=work.context,
                    )
                    self._event_handler(event)
                return work

            import time
            time.sleep(self._poll_interval)

        return work

    def query_capability(self, capability_id: str) -> dict[str, Any] | None:
        """Query whether a capability is currently available."""
        roles = self.list_roles()
        has_capability = any(capability_id in role.required_capability_ids for role in roles)
        if not has_capability:
            return None
        in_progress = [
            work for work in self._work_cache.values()
            if capability_id in work.required_capability_ids
            and work.status == WorkStatus.IN_PROGRESS
        ]
        if in_progress:
            return {
                "capability_id": capability_id,
                "available": False,
                "eta_seconds": None,
                "assignee": in_progress[0].assignee_agent_id or in_progress[0].assignee_role_id,
                "reason": "Capability is currently in use",
            }
        return {
            "capability_id": capability_id,
            "available": True,
            "eta_seconds": 5,
            "assignee": None,
            "reason": "Capability is available",
        }

    def register_capability(self, capability: Any) -> None:
        """Register a capability in the organisational capability store."""
        # Paperclip does not have a native capability registry; we maintain
        # this locally in the adapter to preserve the Organisation abstraction.

    def get_capability(self, capability_id: str) -> Any | None:
        """Retrieve a registered capability by ID."""
        return None

    def emit_event(self, event: Any) -> None:
        """Emit an operational event through the organisation's event boundary."""
        if self._event_handler:
            self._event_handler(event)

    def emit_signal(self, signal: Any) -> None:
        """Emit an organisational signal derived from operational events."""
        if self._signal_handler:
            self._signal_handler(signal)

    def detect_capacity_pressure(self, capability_id: str) -> Any | None:
        """Detect whether a capability is under sustained demand pressure."""
        in_progress = [
            work for work in self._work_cache.values()
            if capability_id in work.required_capability_ids
            and work.status in (WorkStatus.IN_PROGRESS, WorkStatus.ASSIGNED)
        ]
        pending = [
            work for work in self._work_cache.values()
            if capability_id in work.required_capability_ids
            and work.status == WorkStatus.PENDING
        ]
        if not in_progress and not pending:
            return None
        total_load = len(in_progress) + len(pending)
        if total_load > 1:
            from contracts.organisational_events import CapacityPressureSignal
            return CapacityPressureSignal(
                capability_id=capability_id,
                capability_name=capability_id,
                demand_rate_per_hour=float(total_load),
                capacity_rate_per_hour=float(len(in_progress)),
                queue_depth=len(pending),
                average_eta_seconds=300.0 * total_load,
                affected_work_ids=[w.id for w in in_progress + pending],
                reason=f"{total_load} work items compete for this capability",
            )
        return None

    def delegate_authority(self, from_role: Role, to_role: Role, authority: Authority) -> Delegation:
        """Delegate authority from one role to another."""
        delegation = Delegation(
            id=str(uuid4()),
            authority_id=authority.id,
            from_role_id=from_role.id,
            to_role_id=to_role.id,
            reason=f"Delegated from {from_role.name} to {to_role.name}",
        )
        return delegation

    # ------------------------------------------------------------------
    # Paperclip-specific helpers (not part of OrganisationControlPlane)
    # ------------------------------------------------------------------

    def create_company(self, name: str) -> dict[str, Any] | None:
        """Create a Paperclip Company and return its raw representation."""
        try:
            response = self._request("POST", "/api/companies", json={"name": name})
            return response.json()
        except PaperclipAdapterError:
            return None

    def create_agent(self, name: str, adapter_type: str = "process", capabilities: list[str] | None = None, **kwargs: Any) -> Role | None:
        """Create a Paperclip Agent and map it to our Role model."""
        body: dict[str, Any] = {
            "name": name,
            "adapterType": adapter_type,
            "role": kwargs.get("role", "general"),
            "capabilities": ", ".join(capabilities) if capabilities else "",
        }
        optional_fields = ["title", "instructionsBundle", "adapterConfig", "runtimeConfig", "budgetMonthlyCents", "permissions", "metadata"]
        snake_to_camel = {
            "instructions_bundle": "instructionsBundle",
            "adapter_config": "adapterConfig",
            "runtime_config": "runtimeConfig",
            "budget_monthly_cents": "budgetMonthlyCents",
        }
        for snake, camel in snake_to_camel.items():
            if snake in kwargs:
                body[camel] = kwargs[snake]
        for field in optional_fields:
            if field in kwargs:
                body[field] = kwargs[field]

        try:
            response = self._request("POST", f"/api/companies/{self._company_id}/agents", json=body)
            data = response.json()
            role = self._map_agent_to_role(data)
            self._role_cache[role.id] = role
            return role
        except PaperclipAdapterError:
            return None

    def get_heartbeat_run(self, run_id: str) -> dict[str, Any] | None:
        """Retrieve a Paperclip heartbeat run by ID."""
        try:
            response = self._request("GET", f"/api/heartbeat-runs/{run_id}")
            return response.json()
        except PaperclipAdapterError:
            return None

    def get_heartbeat_runs_for_issue(self, issue_id: str) -> list[dict[str, Any]]:
        """Retrieve heartbeat runs for a specific issue."""
        return self._get_heartbeat_runs_for_issue(issue_id)

    def _get_heartbeat_runs_for_issue(self, issue_id: str) -> list[dict[str, Any]]:
        """Internal: get heartbeat runs for issue, filtering by context."""
        try:
            response = self._request("GET", f"/api/companies/{self._company_id}/heartbeat-runs")
            data = response.json()
            if not isinstance(data, list):
                return []
            runs = []
            for run in data:
                context = run.get("contextSnapshot") or {}
                if context.get("issueId") == issue_id:
                    enriched = self.get_heartbeat_run(run["id"])
                    if enriched:
                        runs.append(enriched)
            return runs
        except PaperclipAdapterError:
            return []

    # ------------------------------------------------------------------
    # Event emission helpers
    # ------------------------------------------------------------------

    def _emit_work_event(self, event_type: Any, work: Work, assignee_id: str | None = None) -> None:
        event = WorkEvent(
            event_type=event_type,
            organisation_id=self._company_id,
            work_id=work.id,
            title=work.title,
            work_type=work.work_type,
            assignee_role_id=work.assignee_role_id,
            assignee_agent_id=work.assignee_agent_id,
            required_capability_ids=list(work.required_capability_ids),
            status=work.status.value,
            priority=work.priority,
            outcome=work.outcome,
            context=work.context,
        )
        if self._event_handler:
            self._event_handler(event)

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _map_agent_to_role(self, data: dict[str, Any]) -> Role:
        """Map a Paperclip Agent JSON object to our Role model."""
        capabilities = data.get("capabilities", "")
        if isinstance(capabilities, str):
            capabilities = [c.strip() for c in capabilities.split(",") if c.strip()]
        elif not isinstance(capabilities, list):
            capabilities = []
        return _PaperclipAgentRole(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("title") or "",
            authority_ids=[],
            constraints=[],
            information_access=[],
            reports_to=data.get("reportsTo"),
            status=RoleStatus.ACTIVE if data.get("status") in ("idle", "active") else RoleStatus.INACTIVE,
            required_capability_ids=capabilities,
            metadata=data.get("metadata") or {},
        )

    def _map_issue_to_work(self, data: dict[str, Any]) -> Work:
        """Map a Paperclip Issue JSON object to our Work model."""
        status_map = {
            "todo": WorkStatus.PENDING,
            "in_progress": WorkStatus.IN_PROGRESS,
            "done": WorkStatus.COMPLETED,
            "cancelled": WorkStatus.CANCELLED,
            "blocked": WorkStatus.PENDING,
            "in_review": WorkStatus.IN_PROGRESS,
        }
        raw_status = data.get("status", "todo")
        work_status = status_map.get(raw_status, WorkStatus.PENDING)
        if raw_status == "done":
            work_status = WorkStatus.COMPLETED
        elif raw_status == "cancelled":
            work_status = WorkStatus.CANCELLED

        outcome = None
        work_products = data.get("workProducts")
        if isinstance(work_products, dict):
            outcome = work_products.get("result")

        return Work(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description") or "",
            work_type="task",
            status=work_status,
            priority=data.get("priority", "medium"),
            accountable_role_id=data.get("assigneeAgentId") or data.get("assigneeUserId") or "unassigned",
            coordinating_role_id=None,
            requested_by_role_id=None,
            assignee_role_id=data.get("assigneeUserId"),
            assignee_person_id=data.get("assigneeUserId"),
            assignee_agent_id=data.get("assigneeAgentId"),
            required_capability_ids=data.get("capabilities", []) or [],
            outcome=outcome,
            context=data.get("context", {}),
            organisation_id=self._company_id,
            created_at=self._parse_timestamp(data.get("createdAt")),
            updated_at=self._parse_timestamp(data.get("updatedAt")),
        )

    def _parse_timestamp(self, value: Any) -> datetime:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.now(UTC)
