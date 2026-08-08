"""
Tests for knowledge-mcp configuration contracts.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from configuration.contracts.v1.knowledge import KnowledgeConfiguration


class TestKnowledgeConfiguration:
    def test_type_id(self):
        assert KnowledgeConfiguration.type_id() == "knowledge"

    def test_purpose(self):
        assert KnowledgeConfiguration.purpose() == "Knowledge MCP server behavioral configuration"

    def test_owner(self):
        assert KnowledgeConfiguration.owner() == "platform"

    def test_lifecycle(self):
        lc = KnowledgeConfiguration.lifecycle()
        assert lc.platform == "platform"
        assert lc.capability == "knowledge"
        assert lc.execution == "runtime"

    def test_documentation(self):
        assert KnowledgeConfiguration.documentation() == "Configuration for the knowledge MCP server"

    def test_resolves_with_all_fields(self):
        cfg = KnowledgeConfiguration.model_validate({
            "KNOWLEDGE_CORPUS_ROOT": "/tmp/docs",
            "KNOWLEDGE_CHUNK_SIZE": "400",
            "KNOWLEDGE_CHUNK_OVERLAP": "100",
            "KNOWLEDGE_CONTEXT_CHUNKS": "8",
            "KNOWLEDGE_BUNDLE_BUDGET_TOKENS": "8000",
            "KNOWLEDGE_WATCHER_ENABLED": "true",
            "KNOWLEDGE_INDEX_STATE_PATH": ".knowledge/state.json",
        })
        assert cfg.corpus_root == "/tmp/docs"
        assert cfg.chunk_size == 400
        assert cfg.chunk_overlap == 100
        assert cfg.context_chunks == 8
        assert cfg.bundle_budget_tokens == 8000
        assert cfg.watcher_enabled is True
        assert cfg.index_state_path == ".knowledge/state.json"

    def test_defaults_when_only_required_field(self):
        cfg = KnowledgeConfiguration.model_validate({
            "KNOWLEDGE_CORPUS_ROOT": "/tmp/docs",
        })
        assert cfg.corpus_root == "/tmp/docs"
        assert cfg.chunk_size == 500
        assert cfg.chunk_overlap == 120
        assert cfg.context_chunks == 6
        assert cfg.bundle_budget_tokens == 6000
        assert cfg.watcher_enabled is False
        assert cfg.index_state_path == ".knowledge/state.json"

    def test_missing_corpus_root_raises(self):
        with pytest.raises(ValidationError):
            KnowledgeConfiguration.model_validate({})

    def test_immutable(self):
        cfg = KnowledgeConfiguration.model_validate({
            "KNOWLEDGE_CORPUS_ROOT": "/tmp/docs",
        })
        with pytest.raises(ValidationError):
            cfg.corpus_root = "/other"
