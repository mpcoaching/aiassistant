"""
KnowledgeChunk model.

A deterministic, serializable representation of a parsed and chunked Markdown
document section. Carries enough provenance for later embedding, Qdrant
storage, and MCP retrieval.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    chunk_id: str = Field(description="Deterministic chunk identifier")
    document_path: str = Field(description="Relative path from corpus root")
    content: str = Field(description="Chunk text used for embedding/retrieval")
    section_heading: str | None = Field(default=None, description="Current section heading text")
    breadcrumb: str | None = Field(default=None, description="Full heading hierarchy breadcrumb")
    start_line: int = Field(description="1-based start line in original Markdown")
    end_line: int = Field(description="1-based end line in original Markdown")
    references: list[str] = Field(default_factory=list, description="Extracted document references")
    document_metadata: dict[str, str] = Field(default_factory=dict, description="Frontmatter metadata")
