"""
TDD tests for the Event Bus topology and Knowledge routing (Phase 1, C5 / P1.4 / P1.5).

Behaviour (SA-CONTRACTS-PHASE1.md C5, C6):
- EventBus declares the capability.mode and knowledge.mode exchanges/queues
  (capability.request / capability.reply, knowledge.chunk.discovered) in
  addition to the existing workflow.mode topology.
- CapabilityRequest / CapabilityReply envelopes are serialisable and carry
  correlation_id (Tier 2 in-process and Tier 3 bus use the SAME envelope).
- A KnowledgeSubscriber routes a KnowledgeChunkDiscovered to the correct store
  by semantic tag:
    kind=solved_approach|adr|playbook|policy -> enterprise_concepts (Postgres)
    embedding|similarity                  -> qdrant
    authored_doc                         -> repo_markdown
  without needing a live bus (tested via the routing rule directly + a captured
  publish).

The bus is exercised with a fake connection so no RabbitMQ is required.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

import bus
from bus import CAPABILITY_EXCHANGE, KNOWLEDGE_EXCHANGE, EventBus
from knowledge import KnowledgeChunk, KnowledgeStore, route_by_tags


# ---- bus topology declaration (C5) ----------------------------------------

def test_bus_declares_capability_and_knowledge_topology() -> None:
    _bus = EventBus(url="amqp://guest:guest@localhost:5672/")
    assert CAPABILITY_EXCHANGE == "capability.mode"
    assert KNOWLEDGE_EXCHANGE == "knowledge.mode"
    # topology dict now includes capability + knowledge queues
    assert "capability.request" in bus.CAPABILITY_ROUTING_KEYS
    assert "capability.reply" in bus.CAPABILITY_ROUTING_KEYS
    assert "knowledge.chunk.discovered" in bus.KNOWLEDGE_ROUTING_KEYS


def test_bus_declare_topology_registers_new_exchanges(tmp_path: Path) -> None:
    # Use a fake connection that records exchange/queue declarations.
    bus = EventBus(url="amqp://guest:guest@localhost:5672/")

    class _FakeCh:
        def __init__(self):
            self.exchanges = []
            self.queues = []
            self.binds = []

        def exchange_declare(self, exchange, exchange_type, durable):
            self.exchanges.append((exchange, exchange_type, durable))

        def queue_declare(self, queue, durable, arguments=None):
            self.queues.append(queue)

        def queue_bind(self, exchange, queue, routing_key):
            self.binds.append((exchange, queue, routing_key))

        def close(self):
            pass

    class _FakeConn:
        def __init__(self, ch):
            self._ch = ch

        def channel(self):
            return self._ch

        def close(self):
            pass

    ch = _FakeCh()
    bus._connect = lambda: _FakeConn(ch)  # type: ignore[assignment]
    bus.declare_topology()
    exchange_names = {e[0] for e in ch.exchanges}
    assert CAPABILITY_EXCHANGE in exchange_names
    assert KNOWLEDGE_EXCHANGE in exchange_names
    assert "capability.request" in [b[2] for b in ch.binds]
    assert "knowledge.chunk.discovered" in [b[2] for b in ch.binds]


# ---- capability envelopes (C5) --------------------------------------------

def test_capability_envelope_roundtrip() -> None:
    req = bus.CapabilityRequest(
        request_id="r1",
        correlation_id="c1",
        capability_id="cap-x",
        capability_name="x",
        inputs={"a": 1},
        caller_session_id="s1",
        transport="tier3_bus",
        timeout_seconds=30,
        context_ref=None,
    )
    rep = bus.CapabilityReply(
        request_id="r1",
        correlation_id="c1",
        status="completed",
        outputs={"y": 2},
        artifacts=[],
        telemetry={"duration_ms": 10},
        error=None,
    )
    # serialisable
    req_json = req.to_json()
    rep_json = rep.to_json()
    assert json.loads(req_json)["correlation_id"] == "c1"
    assert json.loads(rep_json)["status"] == "completed"


# ---- knowledge routing rule (C5 / C6) --------------------------------------

def test_route_by_tags_concept_store() -> None:
    assert route_by_tags(["solved_approach"]) == "enterprise_concepts"
    assert route_by_tags(["adr"]) == "enterprise_concepts"
    assert route_by_tags(["playbook", "policy"]) == "enterprise_concepts"


def test_route_by_tags_qdrant() -> None:
    assert route_by_tags(["embedding"]) == "qdrant"
    assert route_by_tags(["similarity", "x"]) == "qdrant"


def test_route_by_tags_repo_markdown() -> None:
    assert route_by_tags(["authored_doc"]) == "repo_markdown"


# ---- KnowledgeStore ingestion (P1.5) ---------------------------------------

def test_knowledge_store_routes_chunk_to_concept_store(tmp_path: Path) -> None:
    store = KnowledgeStore(data_dir=str(tmp_path))
    handled = []

    def _concept_writer(chunk):
        handled.append(("enterprise_concepts", chunk))

    def _qdrant_writer(chunk):
        handled.append(("qdrant", chunk))

    def _markdown_writer(chunk):
        handled.append(("repo_markdown", chunk))

    store.set_writers(_concept_writer, _qdrant_writer, _markdown_writer)
    chunk = KnowledgeChunk(
        chunk_id="ck1",
        semantic_tags=["solved_approach"],
        payload_ref="store://x",
        source="session",
        source_ref="s1",
    )
    store.ingest(chunk)
    assert handled == [("enterprise_concepts", chunk)]


def test_knowledge_store_routes_embedding_to_qdrant(tmp_path: Path) -> None:
    store = KnowledgeStore(data_dir=str(tmp_path))
    sink = []

    def _q(chunk):
        sink.append(chunk)

    store.set_writers(lambda c: None, _q, lambda c: None)
    store.ingest(
        KnowledgeChunk(chunk_id="ck2", semantic_tags=["embedding"], payload_ref="v://e", source="capability", source_ref="c1")
    )
    assert len(sink) == 1
