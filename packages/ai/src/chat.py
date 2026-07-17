"""
Assistant Chat Service (Phase 6).

Provides the Control Center's assistant chat endpoint. Implements:
1. Natural language intent recognition
2. "Have I done this before?" lookup via ConceptStore
3. Session creation and execution via Pattern Runtime
4. Human-in-the-loop support
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from assistant import AssistantReasoningService, StrategyDecision
from capabilities import CapabilityRegistry, ConceptStore
from concepts import ConceptKind, EnterpriseConcept
from enterprise_context import ContextRecord
from intent import Intent, IntentOrigin
from pathway_runtime import PathwayCallRequest, PathwayRuntime, PathwayResponse, PathwayStatus
from session import Session, SessionStatus, create_session_from_decision
from strategy import ReasoningStrategy

logger = logging.getLogger("ai.chat")


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    message: str
    session_id: str
    status: str
    reasoning: Optional[str] = None
    previous_solution: Optional[Dict[str, Any]] = None
    human_input_request: Optional[Dict[str, Any]] = None
    telemetry: Dict[str, Any] = Field(default_factory=dict)


class AssistantChatService:
    """Chat service that bridges natural language to the reasoning core."""

    def __init__(
        self,
        reasoning_service: Optional[AssistantReasoningService] = None,
        concept_store: Optional[ConceptStore] = None,
        capability_registry: Optional[CapabilityRegistry] = None,
        runtime: Optional[PathwayRuntime] = None,
    ) -> None:
        self._reasoning = reasoning_service or AssistantReasoningService()
        self._store = concept_store or ConceptStore()
        self._registry = capability_registry or CapabilityRegistry(self._store)
        self._runtime = runtime
        self._sessions: Dict[str, Session] = {}

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat message and return a response."""
        intent = Intent(
            id=f"chat-{datetime.now(timezone.utc).timestamp()}",
            origin=IntentOrigin.USER_REQUEST,
            raw={"type": "natural_language", "text": request.message},
            declared_context=request.context,
        )

        decision = self._reasoning.decide(intent)

        previous = self._find_previous_solution(decision)
        if previous:
            return ChatResponse(
                message=f"I've done this before. Last time: {previous.get('summary', 'No summary available')}. Want me to reuse that?",
                session_id=request.session_id or f"ses-{intent.id}",
                status="awaiting_confirmation",
                reasoning=decision.rationale,
                previous_solution=previous,
                telemetry={"match_type": "concept_lookup"},
            )

        session = create_session_from_decision(decision, context=request.context)
        self._sessions[session.id] = session

        if self._runtime and session.pipeline:
            pathway_request = PathwayCallRequest(
                session_id=session.id,
                pattern_step={
                    "pattern_id": decision.pattern_pipeline[0] if decision.pattern_pipeline else "default",
                    "ordered_steps": [
                        {
                            "step_id": step.pattern_id,
                            "role": "assistant",
                            "tools": [],
                            "gate_condition": None,
                        }
                        for step in session.pipeline
                    ],
                },
                context=session.context,
                participants=[{"role": r} for r in decision.participant_roles],
                prompt=request.message,
            )
            response = self._runtime.invoke(pathway_request)

            if response.status == PathwayStatus.WAITING and response.human_input_request:
                return ChatResponse(
                    message=response.human_input_request.get("question", "I need some input to proceed."),
                    session_id=session.id,
                    status="awaiting_human_input",
                    reasoning=decision.rationale,
                    human_input_request=response.human_input_request,
                    telemetry={"runtime": getattr(self._runtime, "id", "unknown")},
                )

            if response.status == PathwayStatus.COMPLETED:
                self._record_solution(decision, response.outputs)
                return ChatResponse(
                    message=f"Done. {response.outputs.get('summary', 'Task completed successfully.')}",
                    session_id=session.id,
                    status="completed",
                    reasoning=decision.rationale,
                    telemetry={"runtime": getattr(self._runtime, "id", "unknown")},
                )

        return ChatResponse(
            message=f"I'll help with that. Strategy: {decision.chosen_strategy.value}. Pipeline: {', '.join(decision.pattern_pipeline)}.",
            session_id=session.id,
            status="pending",
            reasoning=decision.rationale,
            telemetry={"runtime": "none", "reason": "no_runtime_configured"},
        )

    def resume_with_human_input(self, session_id: str, human_response: Dict[str, Any]) -> ChatResponse:
        """Resume a paused session with human input."""
        if self._runtime:
            response = self._runtime.resume(session_id, human_response)
            if response.status == PathwayStatus.COMPLETED:
                return ChatResponse(
                    message=f"Done. {response.outputs.get('summary', 'Task completed successfully.')}",
                    session_id=session_id,
                    status="completed",
                    telemetry={"runtime": getattr(self._runtime, "id", "unknown"), "resumed": True},
                )

        return ChatResponse(
            message="Session resumed.",
            session_id=session_id,
            status="completed",
            telemetry={"runtime": "none"},
        )

    def _find_previous_solution(self, decision: StrategyDecision) -> Optional[Dict[str, Any]]:
        """Check the concept store for a previous similar solution."""
        strategy_tag = f"strategy:{decision.chosen_strategy.value}"
        concepts = self._store.list_by_tag(strategy_tag)
        if not concepts:
            return None

        best = max(concepts, key=lambda c: c.payload.get("maturation_history", {}).get("invocation_count", 0))
        history = best.payload.get("maturation_history", {})
        if history.get("invocation_count", 0) >= 1:
            return {
                "concept_id": best.id,
                "name": best.name,
                "summary": best.payload.get("summary", "Previous solution available"),
                "invocation_count": history.get("invocation_count", 0),
                "last_invoked": str(history.get("last_invoked_at", "")) if history.get("last_invoked_at") else None,
            }
        return None

    def _record_solution(self, decision: StrategyDecision, outputs: Dict[str, Any]) -> None:
        """Record a successful solution in the concept store for future reuse."""
        from datetime import datetime, timezone
        concept = EnterpriseConcept(
            id=f"sol-{datetime.now(timezone.utc).timestamp()}",
            kind=ConceptKind.CAPABILITY,
            name=f"solution-{decision.chosen_strategy.value}",
            description=f"Auto-generated solution for {decision.chosen_strategy.value} strategy",
            tags=["solution", f"strategy:{decision.chosen_strategy.value}"],
            payload={
                "summary": outputs.get("summary", ""),
                "outputs": outputs,
                "strategy": decision.chosen_strategy.value,
                "pattern_pipeline": decision.pattern_pipeline,
                "maturation_history": {
                    "invocation_count": 1,
                    "correction_count": 0,
                    "last_invoked_at": datetime.now(timezone.utc).isoformat(),
                },
            },
        )
        self._store.upsert(concept)
