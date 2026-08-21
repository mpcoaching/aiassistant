"""
Capability matching (Increment 1).

Defines the CapabilityMatcher protocol and HumanSelectionMatcher,
the first implementation that uses a simple deterministic heuristic
to surface relevant candidates for human selection.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from capabilities import Capability
from enterprise_context import ContextRecord
from pydantic import BaseModel


class MatchResult(BaseModel):
    """Result of a capability match attempt."""

    candidates: list[Capability]
    confidence: float
    matcher_id: str
    rationale: str = ""


@runtime_checkable
class CapabilityMatcher(Protocol):
    """Protocol for capability matching implementations."""

    def match(
        self,
        request_text: str,
        context: ContextRecord,
        capabilities: list[Capability],
    ) -> MatchResult:
        ...


class HumanSelectionMatcher:
    """First CapabilityMatcher implementation.

    Uses a simple deterministic heuristic:
    - tokenize request_text into lowercase words
    - a capability is a candidate if its name or any tag appears in the request
    - confidence is always 0.0 because the human makes the final selection
    - if no capability matches the heuristic, candidates is empty
    """

    matcher_id = "human_selection"

    def match(
        self,
        request_text: str,
        context: ContextRecord,
        capabilities: list[Capability],
    ) -> MatchResult:
        tokens = set(request_text.lower().split())
        candidates = []
        for cap in capabilities:
            haystack = f"{cap.name} {cap.description or ''} {' '.join(cap.tags or [])}".lower()
            if any(token in haystack for token in tokens if len(token) > 2):
                candidates.append(cap)

        rationale = (
            "Human selection required — heuristic matched "
            f"{len(candidates)} candidate(s)"
        )
        if not candidates:
            rationale = (
                "No deterministic match found; human must indicate "
                "whether a capability exists or specify a gap"
            )

        return MatchResult(
            candidates=candidates,
            confidence=0.0,
            matcher_id=self.matcher_id,
            rationale=rationale,
        )
