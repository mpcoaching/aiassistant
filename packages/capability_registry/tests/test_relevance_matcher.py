"""
Tests for Increment 21B — RelevanceMatcher.

Verifies that the matcher correctly scores and ranks capabilities
by keyword relevance without changing existing behaviour.
"""

from __future__ import annotations

from capability_matcher import MatchResult
from capabilities import Capability, CapabilityKind, CapabilityStatus
from enterprise_context import ContextRecord

from relevance_matcher import RelevanceMatcher


def _capability(
    name: str,
    description: str = "",
    tags: list[str] | None = None,
    status: CapabilityStatus = CapabilityStatus.ACTIVE,
) -> Capability:
    return Capability(
        id=f"cap-{name}",
        name=name,
        description=description,
        owner="core",
        created_by="test",
        tags=tags or [],
        capability_kind=CapabilityKind.TOOL,
        status=status,
    )


def test_name_matching_ranks_name_match_higher() -> None:
    matcher = RelevanceMatcher()
    caps = [
        _capability("create_test_artifact", description="Creates a test artifact", tags=["test"]),
        _capability("send_email", description="Sends an email notification", tags=["email"]),
    ]
    result = matcher.match("create artifact", ContextRecord(), caps)
    assert result.matcher_id == "relevance"
    assert result.candidates[0].name == "create_test_artifact"
    assert result.confidence > 0.0


def test_description_matching_contributes() -> None:
    matcher = RelevanceMatcher()
    caps = [
        _capability("send_email", description="Send email notifications to users", tags=[]),
    ]
    result = matcher.match("send email", ContextRecord(), caps)
    assert len(result.candidates) == 1
    assert result.candidates[0].name == "send_email"
    assert result.confidence > 0.0


def test_tag_matching_contributes() -> None:
    matcher = RelevanceMatcher()
    caps = [
        _capability("analyse_data", description="Analyse data", tags=["data", "analysis"]),
    ]
    result = matcher.match("analyse data", ContextRecord(), caps)
    assert len(result.candidates) == 1
    assert result.confidence > 0.0


def test_deprecated_capabilities_are_excluded() -> None:
    matcher = RelevanceMatcher()
    caps = [
        _capability("create_test_artifact", status=CapabilityStatus.DEPRECATED),
        _capability("send_email", status=CapabilityStatus.ACTIVE),
    ]
    result = matcher.match("create artifact", ContextRecord(), caps)
    assert all(cap.name != "create_test_artifact" for cap in result.candidates)


def test_ranking_by_score() -> None:
    matcher = RelevanceMatcher()
    caps = [
        _capability("create_test_artifact", description="Creates a test artifact", tags=["test"]),
        _capability("create_lead", description="Create a new lead record", tags=["lead"]),
    ]
    result = matcher.match("create test artifact", ContextRecord(), caps)
    assert result.candidates[0].name == "create_test_artifact"
    assert result.candidates[1].name == "create_lead"
    assert result.confidence > 0.0


def test_confidence_in_valid_range() -> None:
    matcher = RelevanceMatcher()
    caps = [_capability("create_test_artifact")]
    result = matcher.match("create artifact", ContextRecord(), caps)
    assert 0.0 <= result.confidence <= 1.0


def test_stronger_match_produces_higher_confidence() -> None:
    matcher = RelevanceMatcher()
    caps_strong = [_capability("create_test_artifact", description="Create test artifact", tags=["test", "artifact"])]
    caps_weak = [_capability("send_email", description="Send email", tags=["email"])]

    result_strong = matcher.match("create test artifact", ContextRecord(), caps_strong)
    result_weak = matcher.match("create test artifact", ContextRecord(), caps_weak)

    assert result_strong.confidence > result_weak.confidence


def test_rationale_describes_keyword_relevance() -> None:
    matcher = RelevanceMatcher()
    caps = [_capability("create_test_artifact")]
    result = matcher.match("create artifact", ContextRecord(), caps)
    assert "keyword relevance" in result.rationale


def test_empty_catalogue() -> None:
    matcher = RelevanceMatcher()
    result = matcher.match("create artifact", ContextRecord(), [])
    assert result.candidates == []
    assert result.confidence == 0.0


def test_no_match() -> None:
    matcher = RelevanceMatcher()
    caps = [_capability("send_email", description="Send email", tags=["email"])]
    result = matcher.match("create artifact", ContextRecord(), caps)
    assert result.candidates == []
    assert result.confidence == 0.0


def test_matcher_id() -> None:
    matcher = RelevanceMatcher()
    caps = [_capability("create_test_artifact")]
    result = matcher.match("create artifact", ContextRecord(), caps)
    assert result.matcher_id == "relevance"


def test_deterministic_ordering() -> None:
    matcher = RelevanceMatcher()
    caps = [
        _capability("alpha", description="alpha", tags=["alpha"]),
        _capability("beta", description="beta", tags=["beta"]),
    ]
    result = matcher.match("alpha beta", ContextRecord(), caps)
    names = [cap.name for cap in result.candidates]
    assert names == sorted(names)
