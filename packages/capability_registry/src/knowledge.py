"""
Knowledge & Concept Store — ingestion router (Phase 1, C5 / C6 / P1.5).

The epistemic Knowledge graph is populated by ``KnowledgeChunkDiscovered``
events. A background subscriber routes each chunk to the correct store based on
semantic tags (anchor §9.2):

  kind=solved_approach | adr | playbook | policy -> enterprise_concepts (Postgres)
  embedding | similarity                          -> qdrant (vector layer)
  authored_doc                                 -> repo_markdown

The routing rule (``route_by_tags``) is pure and tested without a live bus.
``KnowledgeStore`` applies the rule through injected writers so it is testable
and swap-free.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from pydantic import BaseModel, Field


class KnowledgeChunk(BaseModel):
    chunk_id: str
    semantic_tags: List[str]
    payload_ref: str
    source: str  # session | capability | external
    source_ref: str
    access_level: str = "internal"  # public | internal | restricted
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeChunkDiscovered(BaseModel):
    """Event published on the bus when a new KnowledgeChunk is discovered."""
    event_id: str
    chunk: KnowledgeChunk
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def route_by_tags(tags: List[str]) -> str:
    """Map semantic tags to the target store (anchor §9.2)."""
    concept_tags = {"solved_approach", "adr", "playbook", "policy"}
    qdrant_tags = {"embedding", "similarity"}
    markdown_tags = {"authored_doc"}
    if any(t in concept_tags for t in tags):
        return "enterprise_concepts"
    if any(t in qdrant_tags for t in tags):
        return "qdrant"
    if any(t in markdown_tags for t in tags):
        return "repo_markdown"
    # default: durable concept store
    return "enterprise_concepts"


class KnowledgeStore:
    """Ingests KnowledgeChunkDiscovered events and routes by semantic tag."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self._data_dir = Path(data_dir or ".")
        self._concept_writer: Callable[[KnowledgeChunk], None] = lambda c: None
        self._qdrant_writer: Callable[[KnowledgeChunk], None] = lambda c: None
        self._markdown_writer: Callable[[KnowledgeChunk], None] = lambda c: None

    def set_writers(
        self,
        concept_writer: Callable[[KnowledgeChunk], None],
        qdrant_writer: Callable[[KnowledgeChunk], None],
        markdown_writer: Callable[[KnowledgeChunk], None],
    ) -> None:
        self._concept_writer = concept_writer
        self._qdrant_writer = qdrant_writer
        self._markdown_writer = markdown_writer

    def ingest(self, chunk: KnowledgeChunk) -> str:
        target = route_by_tags(chunk.semantic_tags)
        if target == "qdrant":
            self._qdrant_writer(chunk)
        elif target == "repo_markdown":
            self._markdown_writer(chunk)
        else:
            self._concept_writer(chunk)
        self._index_file(chunk)
        return target

    def index(self, chunks: List[KnowledgeChunk]) -> None:
        for chunk in chunks:
            self.ingest(chunk)

    def _index_file(self, chunk: KnowledgeChunk) -> None:
        index_path = self._data_dir / "knowledge_index.jsonl"
        try:
            with open(index_path, "a") as f:
                f.write(json.dumps(chunk.model_dump(mode="json")) + "\n")
        except OSError:
            pass

    def search(self, query: str, tags: Optional[List[str]] = None, access_level: Optional[str] = None) -> List[KnowledgeChunk]:
        results: List[KnowledgeChunk] = []
        index_path = self._data_dir / "knowledge_index.jsonl"
        if not index_path.exists():
            return results
        try:
            with open(index_path) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        chunk = KnowledgeChunk(**data)
                    except (json.JSONDecodeError, ValueError, TypeError):
                        continue
                    if access_level and chunk.access_level != access_level:
                        continue
                    if tags and not any(t in chunk.semantic_tags for t in tags):
                        continue
                    if query.lower() in chunk.payload_ref.lower() or query.lower() in chunk.chunk_id.lower():
                        results.append(chunk)
        except OSError:
            pass
        return results
