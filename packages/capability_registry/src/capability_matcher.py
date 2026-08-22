"""
Capability matching (Increment 1).

Defines the CapabilityMatcher protocol and HumanSelectionMatcher,
the first implementation that presents available capabilities for human
selection without performing automated semantic matching.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from capability import Capability
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

    Performs no automated matching. Returns all available capabilities
    so a human can select the appropriate one or indicate that none
    matches the request.
    """

    matcher_id = "human_selection"

    def match(
        self,
        request_text: str,
        context: ContextRecord,
        capabilities: list[Capability],
    ) -> MatchResult:
        return MatchResult(
            candidates=list(capabilities),
            confidence=0.0,
            matcher_id=self.matcher_id,
            rationale=(
                "Human selection required — no automated matching in first slice"
            ),
        )
