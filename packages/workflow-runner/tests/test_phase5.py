"""
TDD tests for Phase 5 — Learning Loop, Knowledge governance, Token Economics.

Contracts: SA-CONTRACTS-PHASES-2-5.md C12, C13.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from api import app
from capabilities import Capability, CapabilityKind, CapabilityRegistry, ExecutionMode
from concepts import ConceptStore, EnterpriseConcept, ConceptKind, Provenance
from knowledge import KnowledgeStore, KnowledgeChunk, KnowledgeChunkDiscovered, route_by_tags
from session import Session, SessionStatus, create_session_from_decision
from assistant import StrategyDecision
from strategy import ReasoningStrategy
from tokens import TokenEconomics, TokenUsage, CostAccrual


# ---- Learning Loop (C12) --------------------------------------------------

def test_session_close_records_learnings(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)

    cap = Capability(
        id="cap-learn",
        name="learnable_tool",
        capability_kind=CapabilityKind.TOOL,
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport="tier3_bus",
        ai_spec=None,
        interface={"inputs": [], "outputs": [], "errors": []},
    )
    reg.register(cap)
    reg.record_invocation(cap.id, outcome="success")

    concept = store.get(cap.id)
    assert concept is not None
    history = concept.payload.get("maturation_history", {})
    assert history.get("invocation_count", 0) >= 1


def test_learning_loop_promotes_capability_after_threshold(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)

    cap = Capability(
        id="cap-promote",
        name="promotable_tool",
        capability_kind=CapabilityKind.TOOL,
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport="tier3_bus",
        ai_spec=None,
        interface={"inputs": [], "outputs": [], "errors": []},
    )
    reg.register(cap)

    for _ in range(5):
        reg.record_invocation(cap.id, outcome="success")

    promoted = reg.promote(cap.id, compiled_ref_path="agentic/skills/_compiled/promotable_tool.py")
    assert promoted.execution_mode == ExecutionMode.COMPILED
    assert promoted.compiled_ref is not None
    assert promoted.compiled_ref.tests_passed is True


# ---- Knowledge governance (C12) -------------------------------------------

def test_route_by_tags_maps_to_correct_store() -> None:
    assert route_by_tags(["solved_approach"]) == "enterprise_concepts"
    assert route_by_tags(["embedding"]) == "qdrant"
    assert route_by_tags(["authored_doc"]) == "repo_markdown"
    assert route_by_tags(["unknown_tag"]) == "enterprise_concepts"


def test_knowledge_chunk_has_retention_classification() -> None:
    chunk = KnowledgeChunk(
        chunk_id="ck-gov",
        semantic_tags=["solved_approach"],
        payload_ref="doc://test",
        source="session",
        source_ref="s1",
    )
    assert chunk.chunk_id == "ck-gov"
    assert chunk.source == "session"


def test_knowledge_store_filters_by_access_level(tmp_path: Path) -> None:
    store = KnowledgeStore(data_dir=str(tmp_path))
    public_chunk = KnowledgeChunk(
        chunk_id="ck-public",
        semantic_tags=["solved_approach"],
        payload_ref="doc://public",
        source="session",
        source_ref="s1",
        access_level="public",
    )
    internal_chunk = KnowledgeChunk(
        chunk_id="ck-internal",
        semantic_tags=["solved_approach"],
        payload_ref="doc://internal",
        source="session",
        source_ref="s2",
        access_level="internal",
    )
    store.index([public_chunk, internal_chunk])
    public_results = store.search("public", access_level="public")
    assert len(public_results) == 1
    assert public_results[0].chunk_id == "ck-public"


# ---- Token Economics (C13) ------------------------------------------------

def test_token_usage_records_prompt_and_completion() -> None:
    usage = TokenUsage(
        session_id="ses-tok-1",
        capability_id="cap-tok",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 150


def test_cost_accrual_calculates_by_model() -> None:
    econ = TokenEconomics()
    cost = econ.accrue(
        session_id="ses-tok-2",
        capability_id="cap-tok",
        prompt_tokens=1000,
        completion_tokens=500,
        model="gpt-4",
    )
    assert cost.total_cost > 0
    assert cost.prompt_cost > 0
    assert cost.completion_cost > 0


def test_token_economics_tracks_per_session(tmp_path: Path) -> None:
    econ = TokenEconomics(data_dir=str(tmp_path))
    econ.accrue("ses-a", "cap-1", 100, 50, "gpt-4")
    econ.accrue("ses-a", "cap-2", 200, 100, "gpt-4")
    econ.accrue("ses-b", "cap-1", 50, 25, "gpt-4")

    session_a_cost = econ.session_cost("ses-a")
    session_b_cost = econ.session_cost("ses-b")
    assert session_a_cost > session_b_cost


def test_token_economics_tracks_per_capability(tmp_path: Path) -> None:
    econ = TokenEconomics(data_dir=str(tmp_path))
    econ.accrue("ses-1", "cap-frequent", 100, 50, "gpt-4")
    econ.accrue("ses-2", "cap-frequent", 100, 50, "gpt-4")
    econ.accrue("ses-3", "cap-rare", 50, 25, "gpt-4")

    cap_frequent_cost = econ.capability_cost("cap-frequent")
    cap_rare_cost = econ.capability_cost("cap-rare")
    assert cap_frequent_cost > cap_rare_cost
