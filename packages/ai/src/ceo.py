"""
CEO Orchestrator Agent (Increment 6, Increment 15 boundary correction).

The CEO is an organisational ROLE, not the central AI agent. CEOAgent consumes
OrganisationControlPlane and EnterpriseInformationPort via dependency injection.
CEO does NOT discover or select capabilities.

Routes all requests through a lightweight CEO node that:
1. Classifies intent
2. Checks enterprise information for known solutions
3. Delegates to the appropriate organisational role
4. Synthesises results back to the user
5. Escalates to human when uncertain or when a capability gap is detected
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from assistant import AssistantReasoningService, StrategyDecision
from intent import Intent, IntentOrigin, ProblemFrame, recognise
from contracts.organisational_context import OrganisationalContextPort
from contracts.enterprise_information import EnterpriseInformationPort

logger = logging.getLogger("ai.ceo")


class CEOAgent:
    """Lightweight orchestrator that sits in front of every request."""

    def __init__(
        self,
        org_context: OrganisationalContextPort,
        reasoning_service: AssistantReasoningService | None = None,
        enterprise_information: EnterpriseInformationPort | None = None,
        confidence_threshold: float = 0.5,
    ) -> None:
        self._org = org_context
        self._reasoning = reasoning_service or AssistantReasoningService()
        self._enterprise_information = enterprise_information
        self._confidence_threshold = confidence_threshold

    def orchestrate(self, request: dict[str, Any]) -> dict[str, Any]:
        """Route a request and return a synthesised response with delegation trace."""
        intent = self._build_intent(request)
        frame = recognise(intent)

        ctx = request.get("context", {})
        self._org.get_context(
            actor_id=ctx.get("actor_id"),
            role_id=ctx.get("role_id"),
        )

        if frame.confidence < self._confidence_threshold:
            return self._escalate_to_human(intent, frame, reason="low_confidence")

        previous = self._find_previous_solution(frame)
        if previous:
            return self._reuse_previous(intent, frame, previous)

        decision = self._reasoning.decide(intent)
        return self._delegate_execution(intent, frame, decision)

    def _build_intent(self, request: dict[str, Any]) -> Intent:
        text = request.get("message", "")
        return Intent(
            id=f"ceo-{datetime.now(timezone.utc).timestamp()}",
            origin=IntentOrigin.USER_REQUEST,
            raw={"type": "natural_language", "text": text},
            declared_context=request.get("context", {}),
        )

    def _find_previous_solution(self, frame: ProblemFrame) -> dict[str, Any] | None:
        strategy_tag = f"strategy:{self._strategy_from_frame(frame)}"
        if self._enterprise_information is None:
            return None
        previous = self._enterprise_information.find_previous_solutions(strategy_tag)
        if previous is None:
            return None
        return {
            "concept_id": previous.concept_id,
            "name": previous.name,
            "summary": previous.summary,
            "invocation_count": previous.invocation_count,
            "last_invoked": previous.last_invoked,
        }

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

    def _escalate_to_human(
        self, intent: Intent, frame: ProblemFrame, reason: str
    ) -> dict[str, Any]:
        logger.info("CEO escalating to human: intent=%s reason=%s", intent.id, reason)
        return {
            "message": "I'm not confident enough to proceed without human guidance.",
            "session_id": f"ses-{intent.id}",
            "status": "awaiting_human_input",
            "reasoning": (
                f"CEO escalation: {reason}. "
                f"Intent classified as {frame.context.problem_context.value} / "
                f"{frame.context.activity_purpose.value} with confidence {frame.confidence:.2f}."
            ),
            "human_input_request": {
                "question": "Please clarify or provide guidance.",
                "context": {
                    "intent_id": intent.id,
                    "problem_context": frame.context.problem_context.value,
                    "activity_purpose": frame.context.activity_purpose.value,
                    "confidence": frame.confidence,
                    "escalation_reason": reason,
                },
                "session_id": f"ses-{intent.id}",
            },
            "telemetry": {
                "ceo_escalated": True,
                "escalation_reason": reason,
                "confidence": frame.confidence,
                "delegated_to": "human",
                "step": "classify",
            },
        }

    def _reuse_previous(
        self, intent: Intent, frame: ProblemFrame, previous: dict[str, Any]
    ) -> dict[str, Any]:
        logger.info("CEO reusing previous solution: intent=%s", intent.id)
        return {
            "message": (
                "I've done this before. Last time: "
                f"{previous.get('summary', 'No summary available')}. "
                "Want me to reuse that?"
            ),
            "session_id": f"ses-{intent.id}",
            "status": "awaiting_confirmation",
            "reasoning": (
                f"CEO reused previous solution for {frame.context.problem_context.value} / "
                f"{frame.context.activity_purpose.value}."
            ),
            "previous_solution": previous,
            "telemetry": {
                "ceo_reused": True,
                "concept_id": previous.get("concept_id"),
                "invocation_count": previous.get("invocation_count", 0),
                "delegated_to": "cache",
                "step": "reuse",
            },
        }

    def _delegate_execution(
        self, intent: Intent, frame: ProblemFrame, decision: StrategyDecision
    ) -> dict[str, Any]:
        logger.info(
            "CEO delegating to execution: intent=%s strategy=%s",
            intent.id,
            decision.chosen_strategy.value,
        )
        return {
            "message": (
                f"I'll help with that. Strategy: {decision.chosen_strategy.value}. "
                f"Pipeline: {', '.join(decision.pattern_pipeline)}."
            ),
            "session_id": f"ses-{intent.id}",
            "status": "pending",
            "reasoning": (
                f"CEO delegated to {decision.chosen_strategy.value} for "
                f"{frame.context.problem_context.value} / "
                f"{frame.context.activity_purpose.value}. "
                f"Rationale: {decision.rationale}"
            ),
            "telemetry": {
                "ceo_delegated": True,
                "delegated_to": decision.chosen_strategy.value,
                "step": "execute",
                "pattern_pipeline": decision.pattern_pipeline,
                "participant_roles": decision.participant_roles,
                "recognition_level": frame.recognition_level.value,
            },
        }
