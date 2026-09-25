"""
Tests for Increment 21A — CapabilityActionPolicy.

Verifies that the policy correctly maps candidates to actions
without changing existing behaviour.
"""

from __future__ import annotations

from capability_action import (
    CapabilityActionPolicy,
    ExecuteCapability,
    AskUserToSelect,
    NoCapabilityMatch,
)
from contracts.capability_discovery import CapabilityCandidate


def _candidate(id: str, name: str, confidence: float = 1.0) -> CapabilityCandidate:
    return CapabilityCandidate(
        id=id,
        name=name,
        description=f"Does {name}",
        kind="tool",
        tags=[],
        execution_mode="ai_mediated",
        confidence=confidence,
    )


def test_no_candidates_returns_no_match() -> None:
    policy = CapabilityActionPolicy()
    action = policy.decide([])
    assert isinstance(action, NoCapabilityMatch)


def test_single_candidate_returns_ask_user() -> None:
    policy = CapabilityActionPolicy()
    candidates = [_candidate("cap-1", "create_test_artifact")]
    action = policy.decide(candidates)
    assert isinstance(action, AskUserToSelect)
    assert len(action.candidates) == 1
    assert action.candidates[0].id == "cap-1"
    assert action.candidates[0].name == "create_test_artifact"
    assert action.interaction == "confirm"


def test_single_candidate_context_not_required() -> None:
    policy = CapabilityActionPolicy()
    candidates = [_candidate("cap-1", "create_test_artifact")]
    action = policy.decide(candidates)
    assert isinstance(action, AskUserToSelect)
    assert action.interaction == "confirm"


def test_multiple_candidates_returns_ask_user() -> None:
    policy = CapabilityActionPolicy()
    candidates = [
        _candidate("cap-a", "capability_a"),
        _candidate("cap-b", "capability_b"),
    ]
    action = policy.decide(candidates)
    assert isinstance(action, AskUserToSelect)
    assert len(action.candidates) == 2
    assert action.candidates[0].id == "cap-a"
    assert action.candidates[1].id == "cap-b"
    assert action.interaction == "select"


def test_three_candidates_returns_ask_user() -> None:
    policy = CapabilityActionPolicy()
    candidates = [
        _candidate("cap-1", "alpha"),
        _candidate("cap-2", "beta"),
        _candidate("cap-3", "gamma"),
    ]
    action = policy.decide(candidates)
    assert isinstance(action, AskUserToSelect)
    assert len(action.candidates) == 3
    assert action.interaction == "select"


def test_single_weak_candidate_returns_ask_user() -> None:
    policy = CapabilityActionPolicy()
    candidates = [_candidate("cap-1", "create_test_artifact", confidence=0.1)]
    action = policy.decide(candidates)
    assert isinstance(action, AskUserToSelect)
    assert len(action.candidates) == 1


def test_legacy_candidate_with_zero_confidence_asks_user() -> None:
    policy = CapabilityActionPolicy()
    candidates = [_candidate("cap-1", "create_test_artifact", confidence=0.0)]
    action = policy.decide(candidates)
    assert isinstance(action, AskUserToSelect)
    assert len(action.candidates) == 1
