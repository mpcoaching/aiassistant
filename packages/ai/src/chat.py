"""
Assistant Chat Service (Phase 6, Increment 15 boundary correction).

Provides the Control Center's assistant chat endpoint. Implements:
1. Natural language intent recognition
2. Previous solution lookup via EnterpriseInformationPort
3. Capability discovery via CapabilityDiscoveryPort
4. Session creation via SessionFactoryPort
5. Pattern execution via PatternExecutionPort
6. Capability execution via CapabilityExecutionPort
7. Human-in-the-loop support

Assistant is an application-layer translation service. It depends on ports,
not concrete domain-plane implementations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from assistant import AssistantReasoningService
from intent import Intent, IntentOrigin, ProblemFrame, recognise
from pydantic import BaseModel, Field

from contracts.capability_discovery import CapabilityCandidate, CapabilityDiscoveryPort
from contracts.capability_execution import CapabilityExecutionPort, ExecutionResult
from contracts.enterprise_capability_query import CapabilityAvailability, EnterpriseCapabilityQueryPort
from contracts.enterprise_information import EnterpriseInformationPort, SolutionRecord
from contracts.organisational_context import OrganisationalContextPort
from contracts.pattern_execution import PatternExecutionPort, PatternExecutionRequest
from contracts.session_factory import SessionFactoryPort, SessionReference
from contracts.work_management import WorkCreateRequest, WorkManagementPort, WorkReference

from capability_action import CapabilityActionPolicy, ExecuteCapability, AskUserToSelect
from capability_selection_telemetry import CapabilitySelectionTelemetry

logger = logging.getLogger("ai.chat")

# TODO: Replace with a user-facing response policy abstraction.
# This is a temporary proof value for the fast/slow capability decision.
_FAST_ENTERPRISE_ETA_THRESHOLD_SECONDS = 60


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    message: str
    session_id: str
    status: str
    reasoning: str | None = None
    previous_solution: dict[str, Any] | None = None
    human_input_request: dict[str, Any] | None = None
    capability_candidates: list[dict[str, Any]] | None = None
    telemetry: dict[str, Any] = Field(default_factory=dict)
    execution_outputs: dict[str, Any] | None = None
    execution_artifacts: list[str] = Field(default_factory=list)


class AssistantChatService:
    """Application-layer translation service bridging natural language to domain planes."""

    def __init__(
        self,
        reasoning_service: AssistantReasoningService | None = None,
        capability_discovery: CapabilityDiscoveryPort | None = None,
        capability_execution: CapabilityExecutionPort | None = None,
        enterprise_information: EnterpriseInformationPort | None = None,
        organisational_context: OrganisationalContextPort | None = None,
        work_management: WorkManagementPort | None = None,
        session_factory: SessionFactoryPort | None = None,
        pattern_execution: PatternExecutionPort | None = None,
        capability_selection_telemetry: Any | None = None,
        enterprise_capability_query: EnterpriseCapabilityQueryPort | None = None,
    ) -> None:
        self._reasoning = reasoning_service or AssistantReasoningService()
        self._capability_discovery = capability_discovery
        self._capability_execution = capability_execution
        self._enterprise_information = enterprise_information
        self._organisational_context = organisational_context
        self._work_management = work_management
        self._session_factory = session_factory
        self._pattern_execution = pattern_execution
        self._sessions: dict[str, SessionReference] = {}
        self._action_policy = CapabilityActionPolicy()
        self._capability_selection_telemetry = capability_selection_telemetry
        self._enterprise_capability_query = enterprise_capability_query

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat message and return a response."""
        intent = Intent(
            id=f"chat-{datetime.now(timezone.utc).timestamp()}",
            origin=IntentOrigin.USER_REQUEST,
            raw={"type": "natural_language", "text": request.message},
            declared_context=request.context,
        )

        frame = recognise(intent)
        session_id = request.session_id or f"ses-{intent.id}"

        if self._enterprise_information is not None:
            strategy_tag = f"strategy:{self._strategy_from_frame(frame)}"
            previous = self._enterprise_information.find_previous_solutions(strategy_tag)
            if previous is not None:
                return ChatResponse(
                    message=f"I've done this before. Last time: {previous.summary}. Want me to reuse that?",
                    session_id=session_id,
                    status="awaiting_confirmation",
                    reasoning=f"Found previous solution for {strategy_tag}",
                    previous_solution=previous.model_dump(),
                    telemetry={"match_type": "concept_lookup"},
                )

        if self._capability_discovery is not None:
            candidates = self._capability_discovery.find_capabilities(
                request_text=request.message,
                context=frame.context,
            )

            enterprise_response = self._evaluate_enterprise_action(candidates, intent, frame, session_id)
            if enterprise_response is not None:
                return enterprise_response

            action = self._action_policy.decide(candidates, request.context)
            if isinstance(action, ExecuteCapability):
                return self._execute_capability_response(intent, frame, action.candidate, session_id)
            if isinstance(action, AskUserToSelect):
                return self._capability_selection_response(intent, frame, action.candidates, action.interaction, session_id)
            # NoCapabilityMatch falls through to pattern execution

        decision = self._reasoning.decide(intent)

        session = None
        if self._session_factory is not None:
            session = self._session_factory.create_session(
                strategy=decision.chosen_strategy.value,
                pattern_pipeline=decision.pattern_pipeline,
                context=request.context,
            )
            self._sessions[session.session_id] = session

        if session is not None and session.pipeline and self._pattern_execution is not None:
            pattern_request = PatternExecutionRequest(
                session_id=session.session_id,
                pattern_step={
                    "pattern_id": decision.pattern_pipeline[0] if decision.pattern_pipeline else "default",
                    "ordered_steps": [
                        {
                            "step_id": step_id,
                            "role": "assistant",
                            "tools": [],
                            "gate_condition": None,
                        }
                        for step_id in session.pipeline
                    ],
                },
                context=request.context,
                participants=[{"role": r} for r in decision.participant_roles],
                prompt=request.message,
            )
            response = self._pattern_execution.execute_pattern(pattern_request)

            if response.status == "waiting" and response.human_input_request:
                return ChatResponse(
                    message=response.human_input_request.get("question", "I need some input to proceed."),
                    session_id=session.session_id,
                    status="awaiting_human_input",
                    reasoning=decision.rationale,
                    human_input_request=response.human_input_request,
                    telemetry={"runtime": "pattern_execution_port"},
                )

            if response.status == "completed":
                if self._enterprise_information is not None:
                    self._enterprise_information.record_solution(
                        SolutionRecord(
                            summary=response.outputs.get("summary", ""),
                            outputs=response.outputs,
                            strategy=decision.chosen_strategy.value,
                            pattern_pipeline=decision.pattern_pipeline,
                        )
                    )
                return ChatResponse(
                    message=f"Done. {response.outputs.get('summary', 'Task completed successfully.')}",
                    session_id=session.session_id,
                    status="completed",
                    reasoning=decision.rationale,
                    telemetry={"runtime": "pattern_execution_port"},
                )

        # No pattern execution path available — delegate to the Organisation if possible
        if self._work_management is not None:
            return self._delegate_work_response(intent, frame, session_id)

        return ChatResponse(
            message=f"I'll help with that. Strategy: {decision.chosen_strategy.value}. Pipeline: {', '.join(decision.pattern_pipeline)}.",
            session_id=session.session_id if session else f"ses-{intent.id}",
            status="pending",
            reasoning=decision.rationale,
            telemetry={"runtime": "none", "reason": "no_pattern_execution_configured"},
        )

    def resume_with_human_input(self, session_id: str, human_response: dict[str, Any]) -> ChatResponse:
        """Resume a paused session with human input."""
        if self._pattern_execution is not None:
            response = self._pattern_execution.resume_pattern(session_id, human_response)
            if response.status == "completed":
                return ChatResponse(
                    message=f"Done. {response.outputs.get('summary', 'Task completed successfully.')}",
                    session_id=session_id,
                    status="completed",
                    telemetry={"runtime": "pattern_execution_port", "resumed": True},
                )

        return ChatResponse(
            message="Session resumed.",
            session_id=session_id,
            status="completed",
            telemetry={"runtime": "none"},
        )

    def execute_selected_capability(
        self,
        capability_id: str,
        context: dict[str, Any],
    ) -> ExecutionResult:
        """Execute a capability selected by the caller."""
        if self._capability_execution is None:
            raise ValueError("CapabilityExecutionPort not configured")
        return self._capability_execution.execute(
            capability_id=capability_id,
            context=context,
            actor_context={},
        )

    def record_capability_feedback(
        self,
        match_event_id: str,
        user_action: str,
        selected_capability_id: str | None = None,
    ) -> None:
        """Record user feedback on a previously presented capability candidate set."""
        if self._capability_selection_telemetry is not None:
            self._capability_selection_telemetry.record_user_action(
                event_id=match_event_id,
                user_action=user_action,
                selected_capability_id=selected_capability_id,
            )

    def _strategy_from_frame(self, frame: ProblemFrame) -> str:
        problem = frame.context.problem_context.value
        activity = frame.context.activity_purpose.value
        mapping = {
            ("innovation", "explore"): "research_to_synthesis",
            ("incident", "execute"): "investigate_then_fix",
            ("incident", "investigate"): "investigate_then_fix",
            ("design", "decide"): "deliberate_to_consensus",
            ("decision", "decide"): "deliberate_to_consensus",
            ("compliance", "validate"): "verify_and_assimilate",
            ("learning", "optimise"): "verify_and_assimilate",
            ("unknown", "investigate"): "research_to_synthesis",
            ("routine_operation", "execute"): "recognise_and_reuse",
            ("innovation", "decide"): "deliberate_to_consensus",
            ("compliance", "investigate"): "investigate_then_fix",
        }
        return mapping.get((problem, activity), "research_to_synthesis")

    def _execute_capability_response(
        self,
        intent: Intent,
        frame: ProblemFrame,
        candidate: CapabilityCandidate,
        session_id: str,
    ) -> ChatResponse:
        match_event = None
        if self._capability_selection_telemetry is not None:
            match_event = self._capability_selection_telemetry.record_match_event(
                request_text=intent.raw.get("text", ""),
                session_id=session_id,
                candidates=[candidate],
                interaction_type="confirm",
            )

        if self._capability_execution is None:
            telemetry = {
                "recognition_level": frame.recognition_level.value,
                "capability_id": candidate.id,
                "capability_name": candidate.name,
                "execution_mode": candidate.execution_mode,
            }
            if match_event is not None:
                telemetry["match_event_id"] = match_event.event_id
            return ChatResponse(
                message=f"I found a capability ({candidate.name}) but execution is not configured.",
                session_id=f"ses-{intent.id}",
                status="awaiting_capability_selection",
                reasoning=f"Capability {candidate.name} identified but no execution port available.",
                capability_candidates=[
                    {
                        "id": candidate.id,
                        "name": candidate.name,
                        "description": candidate.description,
                        "kind": candidate.kind,
                        "execution_mode": candidate.execution_mode,
                        "tags": candidate.tags,
                    }
                ],
                telemetry=telemetry,
            )

        result = self.execute_selected_capability(
            capability_id=candidate.id,
            context={},
        )

        if result.telemetry.get("error"):
            message = f"Execution failed: {result.outputs.get('error', result.telemetry['error'])}"
            status = "failed"
        else:
            outputs = result.outputs
            summary = outputs.get("summary") or outputs.get("result") or str(outputs)
            message = f"Executed {candidate.name}. Result: {summary}"
            if result.artifacts:
                message += f" Artifacts: {', '.join(result.artifacts)}"
            status = "completed"

        return ChatResponse(
            message=message,
            session_id=f"ses-{intent.id}",
            status=status,
            reasoning=f"Executed capability {candidate.name} ({candidate.kind}, {candidate.execution_mode})",
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "capability_id": candidate.id,
                "capability_name": candidate.name,
                "execution_mode": candidate.execution_mode,
                "execution_error": result.telemetry.get("error"),
                **({"match_event_id": match_event.event_id} if match_event is not None else {}),
            },
            execution_outputs=result.outputs,
            execution_artifacts=result.artifacts,
        )

    def _capability_selection_response(
        self,
        intent: Intent,
        frame: ProblemFrame,
        candidates: list[CapabilityCandidate],
        interaction: str = "select",
        session_id: str | None = None,
    ) -> ChatResponse:
        """Build a response that exposes capability candidates for human selection or confirmation."""
        if interaction == "confirm" and len(candidates) == 1:
            message = (
                f"I found {candidates[0].name}. "
                f"Shall I proceed with this capability?"
            )
        else:
            message = (
                f"I found {len(candidates)} capabilities that might help. "
                f"Please select one to proceed, or tell me which one to run."
            )

        match_event = None
        if self._capability_selection_telemetry is not None:
            match_event = self._capability_selection_telemetry.record_match_event(
                request_text=intent.raw.get("text", ""),
                session_id=session_id,
                candidates=candidates,
                interaction_type=interaction,
            )

        telemetry = {
            "recognition_level": frame.recognition_level.value,
            "matcher": "human_selection",
            "candidate_count": len(candidates),
            "interaction": interaction,
        }
        if match_event is not None:
            telemetry["match_event_id"] = match_event.event_id

        return ChatResponse(
            message=message,
            session_id=session_id or f"ses-{intent.id}",
            status="awaiting_capability_selection",
            reasoning=(
                f"Recognised as {frame.context.problem_context.value} / "
                f"{frame.context.activity_purpose.value}. "
                f"{len(candidates)} capabilities available."
            ),
            capability_candidates=[
                {
                    "id": cap.id,
                    "name": cap.name,
                    "description": cap.description,
                    "kind": cap.kind,
                    "execution_mode": cap.execution_mode,
                    "tags": cap.tags,
                }
                for cap in candidates
            ],
            telemetry=telemetry,
        )

    def _delegate_work_response(
        self,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
        required_capability_ids: list[str] | None = None,
    ) -> ChatResponse:
        """Delegate work to the Organisation via WorkManagementPort."""
        request_text = intent.raw.get("text", "")
        work_ref = self._work_management.create_work(
            WorkCreateRequest(
                title=request_text[:100],
                description=request_text,
                accountable_role_id="default",
                work_type="project",
                priority="normal",
                organisation_id="default",
                required_capability_ids=required_capability_ids or [],
            )
        )
        return ChatResponse(
            message=f"I've delegated this to the Organisation. Work ID: {work_ref.work_id}. Status: {work_ref.status}.",
            session_id=session_id,
            status="delegated",
            reasoning=(
                f"No capability match. Delegated to Organisation as work "
                f"({frame.context.problem_context.value} / "
                f"{frame.context.activity_purpose.value})."
            ),
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "work_id": work_ref.work_id,
                "work_status": work_ref.status,
                "delegated": True,
                "required_capability_ids": required_capability_ids or [],
            },
        )

    def _evaluate_enterprise_action(
        self,
        candidates: list[CapabilityCandidate],
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
    ) -> ChatResponse | None:
        """Evaluate whether the Organisation can handle this request.

        Returns a ChatResponse if the enterprise should act, otherwise None
        to allow fallback to pattern execution or other paths.
        """
        if self._enterprise_capability_query is None or not candidates:
            return None

        best_candidate = candidates[0]
        availability = self._enterprise_capability_query.query_capability(best_candidate.id)

        if availability is None:
            return self._handle_capability_gap(intent, frame, session_id, best_candidate)

        if not availability.available:
            return self._handle_unavailable_capability(intent, frame, session_id, availability)

        eta = availability.eta_seconds or 0
        if eta <= _FAST_ENTERPRISE_ETA_THRESHOLD_SECONDS:
            return self._handle_fast_capability(best_candidate.id, intent, frame, session_id)

        return self._handle_slow_capability(best_candidate.id, intent, frame, session_id, eta)

    def _handle_fast_capability(
        self,
        capability_id: str,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
    ) -> ChatResponse:
        """Fast enterprise capability: delegate immediately."""
        return self._delegate_work_response(
            intent, frame, session_id, required_capability_ids=[capability_id]
        )

    def _handle_slow_capability(
        self,
        capability_id: str,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
        eta_seconds: int,
    ) -> ChatResponse:
        """Slow enterprise capability: provide interim answer and delegate."""
        self._delegate_work_response(
            intent, frame, session_id, required_capability_ids=[capability_id]
        )
        return ChatResponse(
            message=(
                f"The enterprise can produce the proper answer for this, "
                f"but it will take approximately {eta_seconds} seconds. "
                f"I can give you a preliminary answer now while the enterprise work continues. "
                f"Work has been delegated to the Organisation."
            ),
            session_id=session_id,
            status="delegated_with_interim",
            reasoning=(
                f"Enterprise capability {capability_id} available but ETA {eta_seconds}s exceeds threshold. "
                f"Providing interim response while enterprise work proceeds."
            ),
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "capability_id": capability_id,
                "eta_seconds": eta_seconds,
                "delegated": True,
                "interim": True,
            },
        )

    def _handle_unavailable_capability(
        self,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
        availability: CapabilityAvailability,
    ) -> ChatResponse:
        """Capability exists but is currently unavailable."""
        return ChatResponse(
            message=(
                f"The enterprise has this capability, but it is currently unavailable. "
                f"{availability.reason}. "
                f"I can queue this work for when it becomes available."
            ),
            session_id=session_id,
            status="capability_unavailable",
            reasoning=(
                f"Capability exists but unavailable: {availability.reason}. "
                f"Assignee: {availability.assignee}."
            ),
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "capability_id": availability.capability_id,
                "available": False,
                "assignee": availability.assignee,
                "reason": availability.reason,
            },
        )

    def _handle_capability_gap(
        self,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
        candidate: CapabilityCandidate,
    ) -> ChatResponse:
        """Capability does not exist in the enterprise."""
        work_ref = None
        if self._work_management is not None:
            request_text = intent.raw.get("text", "")
            work_ref = self._work_management.create_work(
                WorkCreateRequest(
                    title=f"Develop capability: {candidate.name}",
                    description=(
                        f"Investigate and develop a capability for: {request_text}\n"
                        f"Missing capability: {candidate.name} ({candidate.id})"
                    ),
                    accountable_role_id="default",
                    work_type="capability_development",
                    priority="normal",
                    organisation_id="default",
                    required_capability_ids=[],
                )
            )

        message = (
            f"The enterprise does not currently have a capability for '{candidate.name}'. "
            f"I can provide a best-effort response"
        )
        if work_ref is not None:
            message += (
                f", and I've initiated work to develop this capability "
                f"(Work ID: {work_ref.work_id})"
            )
        message += "."

        return ChatResponse(
            message=message,
            session_id=session_id,
            status="capability_gap",
            reasoning=(
                f"No enterprise capability found for {candidate.id}. "
                f"This represents a capability gap. "
                f"{'Capability development work created: ' + work_ref.work_id if work_ref else 'No work management available.'}"
            ),
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "capability_id": candidate.id,
                "capability_name": candidate.name,
                "gap": True,
                "work_created": work_ref is not None,
                "work_id": work_ref.work_id if work_ref else None,
            },
        )
