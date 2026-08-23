"""
Capability action policy (Increment 21A — capability decision boundary).

Separates the question "which capabilities match?" (matching, People/Capability)
from "what should we do given those candidates?" (action policy, AI plane).

The policy is stateless and side-effect free. It maps candidates to an action;
it does not call ports, execute capabilities, or manage state.
"""

from __future__ import annotations

from contracts.capability_discovery import CapabilityCandidate


class CapabilityAction:
    """Marker base class for capability actions."""


class ExecuteCapability(CapabilityAction):
    """Execute a single capability directly."""

    def __init__(self, candidate: CapabilityCandidate, context: dict[str, Any]) -> None:
        self.candidate = candidate
        self.context = context


class AskUserToSelect(CapabilityAction):
    """Present candidates to the user for selection."""

    def __init__(self, candidates: list[CapabilityCandidate]) -> None:
        self.candidates = candidates


class NoCapabilityMatch(CapabilityAction):
    """No capabilities match; fall through to reasoning/pattern path."""


class CapabilityActionPolicy:
    """Decides what action to take given capability candidates.

    This is a pure decision function. It does not call ports,
    execute capabilities, or manage state.
    """

    def decide(
        self,
        candidates: list[CapabilityCandidate],
        context: dict[str, Any] | None = None,
    ) -> CapabilityAction:
        if not candidates:
            return NoCapabilityMatch()
        if len(candidates) == 1:
            return ExecuteCapability(candidate=candidates[0], context=context or {})
        return AskUserToSelect(candidates=candidates)
