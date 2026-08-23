"""
In-memory port implementations for Assistant tests.

These fixtures simulate domain-plane behaviour without importing
concrete implementations into the AI production source tree.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contracts.capability_discovery import CapabilityCandidate
from contracts.capability_execution import ExecutionResult
from contracts.enterprise_information import PreviousSolution, SolutionRecord
from contracts.organisational_context import RoleReference
from contracts.pattern_execution import PatternExecutionRequest, PatternExecutionResult
from contracts.session_factory import SessionReference
from contracts.work_management import WorkReference


class InMemoryCapabilityDiscoveryPort:
    def __init__(self, candidates: list[CapabilityCandidate] | None = None) -> None:
        self._candidates = candidates or []

    def list_capabilities(self) -> list[CapabilityCandidate]:
        return list(self._candidates)

    def find_capabilities(self, request_text: str, context: dict[str, Any]) -> list[CapabilityCandidate]:
        return list(self._candidates)


class InMemoryCapabilityExecutionPort:
    def __init__(self, result: ExecutionResult | None = None) -> None:
        self._result = result or ExecutionResult(outputs={"status": "completed"}, artifacts=[], telemetry={})
        self.executed: list[dict[str, Any]] = []

    def execute(self, capability_id: str, context: dict[str, Any], actor_context: dict[str, Any]) -> ExecutionResult:
        self.executed.append({"capability_id": capability_id, "context": context, "actor_context": actor_context})
        return self._result


class InMemoryEnterpriseInformationPort:
    def __init__(self, solutions: list[PreviousSolution] | None = None) -> None:
        self._solutions = list(solutions or [])
        self.recorded: list[SolutionRecord] = []

    def find_previous_solutions(self, strategy_tag: str) -> PreviousSolution | None:
        for sol in self._solutions:
            if sol.name == strategy_tag or sol.concept_id == strategy_tag:
                return sol
        return None

    def record_solution(self, solution: SolutionRecord) -> None:
        self.recorded.append(solution)


class InMemoryOrganisationalContextPort:
    def __init__(self, context: dict[str, Any] | None = None) -> None:
        self._context = context or {}
        self._roles: dict[str, RoleReference] = {}

    def get_context(self, actor_id: str | None, role_id: str | None) -> Any:
        from contracts.organisational_context import OrganisationalContext
        return OrganisationalContext(
            current_actor_id=actor_id or self._context.get("current_actor_id"),
            current_role_id=role_id or self._context.get("current_role_id"),
            reporting_relationships=self._context.get("reporting_relationships", []),
            authority_scope=self._context.get("authority_scope", []),
            organisational_relationships=self._context.get("organisational_relationships", {}),
            capability_gaps=self._context.get("capability_gaps", []),
        )

    def get_role(self, role_id: str) -> RoleReference | None:
        return self._roles.get(role_id)

    def register_role(self, role: RoleReference) -> None:
        self._roles[role.role_id] = role


class InMemoryWorkManagementPort:
    def __init__(self) -> None:
        self._work: dict[str, Any] = {}

    def create_work(self, request: Any) -> WorkReference:
        work_id = f"work-{len(self._work) + 1}"
        self._work[work_id] = request.model_dump()
        return WorkReference(work_id=work_id, status="draft")

    def mark_ready(self, work_id: str) -> WorkReference | None:
        if work_id in self._work:
            self._work[work_id]["status"] = "in_progress"
            return WorkReference(work_id=work_id, status="in_progress")
        return None

    def get_work(self, work_id: str) -> WorkReference | None:
        work = self._work.get(work_id)
        if work is None:
            return None
        return WorkReference(work_id=work_id, status=work.get("status", "unknown"))


class InMemorySessionFactoryPort:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    def create_session(self, strategy: str, pattern_pipeline: list[str], context: dict[str, Any]) -> SessionReference:
        session_id = f"ses-{datetime.now(timezone.utc).timestamp()}"
        session = SessionReference(
            session_id=session_id,
            status="pending",
            pipeline=[{"pattern_id": pid} for pid in pattern_pipeline],
        )
        self.created.append({
            "session_id": session_id,
            "strategy": strategy,
            "pattern_pipeline": pattern_pipeline,
            "context": context,
        })
        return session


class InMemoryPatternExecutionPort:
    def __init__(
        self,
        execute_result: PatternExecutionResult | None = None,
        resume_result: PatternExecutionResult | None = None,
    ) -> None:
        self._execute_result = execute_result or PatternExecutionResult(
            status="completed",
            outputs={"summary": "Pattern completed"},
            artifacts=[],
            telemetry={"runtime": "in_memory"},
        )
        self._resume_result = resume_result or PatternExecutionResult(
            status="completed",
            outputs={"summary": "Resumed and completed"},
            artifacts=[],
            telemetry={"runtime": "in_memory", "resumed": True},
        )
        self.executed: list[PatternExecutionRequest] = []
        self.resumed: list[str] = []

    def execute_pattern(self, request: PatternExecutionRequest) -> PatternExecutionResult:
        self.executed.append(request)
        return self._execute_result

    def resume_pattern(self, session_id: str, human_response: dict[str, Any]) -> PatternExecutionResult:
        self.resumed.append(session_id)
        return self._resume_result
