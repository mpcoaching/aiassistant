"""
Assistant Reasoning Service (Phase 2, contracts C9 / anchor RC-1).

Wires ``recognise`` + ``select_strategy`` into a single ``decide`` entrypoint
that produces a ``StrategyDecision`` — the hand-off to the Workflow Engine
(Phase 3) for Session creation and execution.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from intent import Intent, recognise
from strategy import ReasoningStrategy, StrategyProposal, select_strategy


class StrategyDecision(BaseModel):
    intent_id: str
    chosen_strategy: ReasoningStrategy
    pattern_pipeline: list[str] = Field(default_factory=list)
    participant_roles: list[str] = Field(default_factory=list)
    proposed_session_id: Optional[str] = None
    rationale: str = ""


class AssistantReasoningService:
    """The reasoning entrypoint: Intent -> ProblemFrame -> Strategy -> pipeline."""

    def decide(self, intent: Intent) -> StrategyDecision:
        frame = recognise(intent)
        proposals = select_strategy(frame.context)
        chosen = proposals[0] if proposals else StrategyProposal(
            strategy=ReasoningStrategy.RESEARCH_TO_SYNTHESIS,
            confidence=0.0,
            seed_patterns=[],
            rationale="no proposal matched",
        )
        return StrategyDecision(
            intent_id=intent.id,
            chosen_strategy=chosen.strategy,
            pattern_pipeline=chosen.seed_patterns,
            participant_roles=self._resolve_roles(chosen.strategy),
            rationale=chosen.rationale,
        )

    @staticmethod
    def _resolve_roles(strategy: ReasoningStrategy) -> list[str]:
        role_map = {
            ReasoningStrategy.RECOGNISE_AND_REUSE: ["operator"],
            ReasoningStrategy.INVESTIGATE_THEN_FIX: ["investigator", "operator", "approver"],
            ReasoningStrategy.DELIBERATE_TO_CONSENSUS: ["moderator", "proposer", "critic", "approver"],
            ReasoningStrategy.RESEARCH_TO_SYNTHESIS: ["researcher", "facilitator"],
            ReasoningStrategy.VERIFY_AND_ASSIMILATE: ["validator", "learner"],
        }
        return role_map.get(strategy, ["operator"])
