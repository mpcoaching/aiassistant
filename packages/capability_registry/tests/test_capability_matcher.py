"""
Tests for CapabilityMatcher and HumanSelectionMatcher (Increment 1).
"""

from __future__ import annotations

from pathlib import Path

from capability_matcher import HumanSelectionMatcher, MatchResult
from capabilities import Capability, CapabilityKind, CapabilityRegistry
from capability_registry.src.concept_store_adapter import ConceptStoreCapabilityRepository
from concepts import ConceptStore
from enterprise_context import ContextRecord


def _capability(name: str, tags: list[str] | None = None) -> Capability:
    return Capability(
        id=f"cap-{name}",
        name=name,
        description=f"{name} capability",
        owner="core",
        created_by="test",
        tags=tags or ["test"],
        capability_kind=CapabilityKind.TOOL,
    )


def test_human_selection_matcher_returns_all_capabilities():
    matcher = HumanSelectionMatcher()
    caps = [
        _capability("create_test_artifact", tags=["test", "artifact"]),
        _capability("send_email", tags=["email", "notification"]),
        _capability("analyse_data", tags=["data", "analysis"]),
    ]
    result = matcher.match("weather forecast", ContextRecord(), caps)
    assert len(result.candidates) == 3
    assert result.confidence == 0.0
    assert result.matcher_id == "human_selection"
    assert "Human selection required" in result.rationale


def test_human_selection_matcher_returns_empty_for_empty_catalog():
    matcher = HumanSelectionMatcher()
    result = matcher.match("weather forecast", ContextRecord(), [])
    assert result.candidates == []
    assert result.confidence == 0.0


def test_capability_registry_list_all(tmp_path: Path):
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(ConceptStoreCapabilityRepository(store))
    reg.register(_capability("alpha"))
    reg.register(_capability("beta"))
    all_caps = reg.list_all()
    assert len(all_caps) == 2
    assert {c.name for c in all_caps} == {"alpha", "beta"}


def test_capability_registry_list_all_empty(tmp_path: Path):
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(ConceptStoreCapabilityRepository(store))
    assert reg.list_all() == []


def test_match_result_model():
    result = MatchResult(
        candidates=[],
        confidence=0.0,
        matcher_id="test",
        rationale="ok",
    )
    assert result.confidence == 0.0
    assert result.rationale == "ok"
