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
from contracts.enterprise_information import EnterpriseInformationPort, SolutionRecord
from contracts.organisational_context import OrganisationalContextPort
from contracts.pattern_execution import PatternExecutionPort, PatternExecutionRequest
from contracts.session_factory import SessionFactoryPort, SessionReference
from contracts.work_management import WorkManagementPort

from capability_action import CapabilityActionPolicy, ExecuteCapability, AskUserToSelect

logger = logging.getLogger("ai.chat")


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

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat message and return a response."""
        intent = Intent(
            id=f"chat-{datetime.now(timezone.utc).timestamp()}",
            origin=IntentOrigin.USER_REQUEST,
            raw={"type": "natural_language", "text": request.message},
            declared_context=request.context,
        )

        frame = recognise(intent)

        if self._enterprise_information is not None:
            strategy_tag = f"strategy:{self._strategy_from_frame(frame)}"
            previous = self._enterprise_information.find_previous_solutions(strategy_tag)
            if previous is not None:
                return ChatResponse(
                    message=f"I've done this before. Last time: {previous.summary}. Want me to reuse that?",
                    session_id=request.session_id or f"ses-{intent.id}",
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
            action = self._action_policy.decide(candidates, request.context)
            if isinstance(action, ExecuteCapability):
                return self._execute_capability_response(intent, frame, action.candidate)
            if isinstance(action, AskUserToSelect):
                return self._capability_selection_response(intent, frame, action.candidates)
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
    ) -> ChatResponse:
        if self._capability_execution is None:
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
                telemetry={"recognition_level": frame.recognition_level.value},
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
            },
            execution_outputs=result.outputs,
            execution_artifacts=result.artifacts,
        )

    def _capability_selection_response(
        self,
        intent: Intent,
        frame: ProblemFrame,
        candidates: list[CapabilityCandidate],
    ) -> ChatResponse:
        """Build a response that exposes capability candidates for human selection."""
        return ChatResponse(
            message=f"I found {len(candidates)} capabilities that might help. Please select one to proceed, or tell me which one to run.",
            session_id=f"ses-{intent.id}",
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
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "matcher": "human_selection",
                "candidate_count": len(candidates),
            },
        )
