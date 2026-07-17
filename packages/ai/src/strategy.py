"""
Strategy Selection (Phase 2, contract C4).

The v1 seed is the static Context→Pattern mapping table from the anchor doc §6.
``select_strategy`` returns ranked StrategyProposals. Later versions replace the
table with a learned selector without changing the interface.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from enterprise_context import (
    ActivityPurpose,
    ContextRecord,
    ProblemContext,
)


class ReasoningStrategy(str, Enum):
    RECOGNISE_AND_REUSE = "recognise_and_reuse"
    INVESTIGATE_THEN_FIX = "investigate_then_fix"
    DELIBERATE_TO_CONSENSUS = "deliberate_to_consensus"
    RESEARCH_TO_SYNTHESIS = "research_to_synthesis"
    VERIFY_AND_ASSIMILATE = "verify_and_assimilate"


# v1 seed table (anchor §6): (problem, activity) -> strategy + seed patterns
_STRATEGY_SEED = {
    ("innovation", "explore"): (ReasoningStrategy.RESEARCH_TO_SYNTHESIS, ["brainstorm@1.0.0"]),
    ("incident", "execute"): (ReasoningStrategy.INVESTIGATE_THEN_FIX, ["sop_execution@1.0.0"]),
    ("incident", "investigate"): (ReasoningStrategy.INVESTIGATE_THEN_FIX, ["investigation@1.0.0"]),
    ("design", "decide"): (ReasoningStrategy.DELIBERATE_TO_CONSENSUS, ["debate@1.0.0", "consensus@1.0.0"]),
    ("decision", "decide"): (ReasoningStrategy.DELIBERATE_TO_CONSENSUS, ["consensus@1.0.0"]),
    ("compliance", "validate"): (ReasoningStrategy.VERIFY_AND_ASSIMILATE, ["verification@1.0.0"]),
    ("learning", "optimise"): (ReasoningStrategy.VERIFY_AND_ASSIMILATE, ["reflection@1.0.0", "learning@1.0.0"]),
    ("unknown", "investigate"): (ReasoningStrategy.RESEARCH_TO_SYNTHESIS, ["research@1.0.0", "investigation@1.0.0"]),
    ("routine_operation", "execute"): (ReasoningStrategy.RECOGNISE_AND_REUSE, ["sop_execution@1.0.0"]),
    ("innovation", "decide"): (ReasoningStrategy.DELIBERATE_TO_CONSENSUS, ["debate@1.0.0"]),
    ("compliance", "investigate"): (ReasoningStrategy.INVESTIGATE_THEN_FIX, ["investigation@1.0.0"]),
}


class StrategyProposal(BaseModel):
    strategy: ReasoningStrategy
    confidence: float
    seed_patterns: list[str] = Field(default_factory=list)
    rationale: str = ""


def select_strategy(frame: ContextRecord) -> list[StrategyProposal]:
    key = (frame.problem_context.value, frame.activity_purpose.value)
    strategy, patterns = _STRATEGY_SEED.get(key, (ReasoningStrategy.RESEARCH_TO_SYNTHESIS, ["research@1.0.0"]))
    rationale = f"seed lookup ({key[0]}, {key[1]}) -> {strategy.value}"
    return [StrategyProposal(strategy=strategy, confidence=0.8, seed_patterns=patterns, rationale=rationale)]
