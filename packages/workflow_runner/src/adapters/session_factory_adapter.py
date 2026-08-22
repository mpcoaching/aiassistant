"""
Adapter: contracts.SessionFactoryPort -> workflow_runner Session model.

Translates strategy/pattern_pipeline/context into a SessionReference
by wrapping create_session_from_decision().
"""

from __future__ import annotations

from typing import Any

from assistant import ReasoningStrategy, StrategyDecision
from contracts.session_factory import SessionReference

from session import create_session_from_decision


class SessionFactoryAdapter:
    def create_session(self, strategy: str, pattern_pipeline: list[str], context: dict[str, Any]) -> SessionReference:
        try:
            chosen_strategy = ReasoningStrategy(strategy)
        except ValueError:
            chosen_strategy = ReasoningStrategy.RESEARCH_TO_SYNTHESIS

        decision = StrategyDecision(
            intent_id=f"ses-{context.get('session_id', 'auto')}",
            chosen_strategy=chosen_strategy,
            pattern_pipeline=pattern_pipeline,
            participant_roles=[],
            rationale="",
        )
        session = create_session_from_decision(decision, context)
        return SessionReference(
            session_id=session.id,
            status=session.status.value,
            pipeline=[step.model_dump() for step in session.pipeline],
        )
