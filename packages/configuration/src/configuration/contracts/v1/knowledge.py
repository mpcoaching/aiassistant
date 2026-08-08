"""
Knowledge MCP Configuration Contract.

Defines the behavioral configuration for the knowledge MCP server.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from configuration.contracts.base import Contract, Lifecycle


class KnowledgeConfiguration(Contract, BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    corpus_root: str = Field(validation_alias="KNOWLEDGE_CORPUS_ROOT")
    chunk_size: int = Field(default=500, validation_alias="KNOWLEDGE_CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, validation_alias="KNOWLEDGE_CHUNK_OVERLAP")
    context_chunks: int = Field(default=6, validation_alias="KNOWLEDGE_CONTEXT_CHUNKS")
    bundle_budget_tokens: int = Field(default=6000, validation_alias="KNOWLEDGE_BUNDLE_BUDGET_TOKENS")
    watcher_enabled: bool = Field(default=False, validation_alias="KNOWLEDGE_WATCHER_ENABLED")
    index_state_path: str = Field(default=".knowledge/state.json", validation_alias="KNOWLEDGE_INDEX_STATE_PATH")

    @classmethod
    def type_id(cls) -> str:
        return "knowledge"

    @classmethod
    def purpose(cls) -> str:
        return "Knowledge MCP server behavioral configuration"

    @classmethod
    def owner(cls) -> str:
        return "platform"

    @classmethod
    def lifecycle(cls) -> Lifecycle:
        return Lifecycle(platform="platform", capability="knowledge", execution="runtime")

    @classmethod
    def documentation(cls) -> str:
        return "Configuration for the knowledge MCP server"
