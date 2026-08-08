"""
Tests for Configuration Manager integration.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from configuration import ConfigurationManager, DotEnvProvider
from configuration.contracts.v1.knowledge import KnowledgeConfiguration
from configuration.contracts.v1.qdrant import QdrantConfiguration
from configuration.providers.exceptions import ConfigurationResolutionFailed


class TestKnowledgeConfigurationResolution:
    def test_resolves_with_env_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = os.path.join(tmpdir, ".env")
            with open(env_file, "w") as f:
                f.write("KNOWLEDGE_CORPUS_ROOT=/tmp/docs\n")
                f.write("QDRANT_URL=https://qdrant.local.test\n")
                f.write("QDRANT_KEY=test-key\n")

            manager = ConfigurationManager(DotEnvProvider(env_file=env_file))
            knowledge_cfg = manager.resolve(KnowledgeConfiguration)
            qdrant_cfg = manager.resolve(QdrantConfiguration)

            assert knowledge_cfg.corpus_root == "/tmp/docs"
            assert qdrant_cfg.url == "https://qdrant.local.test"
            assert qdrant_cfg.api_key == "test-key"

    def test_knowledge_defaults_applied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = os.path.join(tmpdir, ".env")
            with open(env_file, "w") as f:
                f.write("KNOWLEDGE_CORPUS_ROOT=/tmp/docs\n")

            manager = ConfigurationManager(DotEnvProvider(env_file=env_file))
            knowledge_cfg = manager.resolve(KnowledgeConfiguration)

            assert knowledge_cfg.chunk_size == 500
            assert knowledge_cfg.chunk_overlap == 120
            assert knowledge_cfg.context_chunks == 6
            assert knowledge_cfg.bundle_budget_tokens == 6000
            assert knowledge_cfg.watcher_enabled is False
            assert knowledge_cfg.index_state_path == ".knowledge/state.json"

    def test_qdrant_default_url_when_not_supplied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = os.path.join(tmpdir, ".env")
            with open(env_file, "w") as f:
                f.write("QDRANT_KEY=test-key\n")

            manager = ConfigurationManager(DotEnvProvider(env_file=env_file))
            qdrant_cfg = manager.resolve(QdrantConfiguration)

            assert qdrant_cfg.url == "https://qdrant.local.test"
            assert qdrant_cfg.api_key == "test-key"

    def test_missing_corpus_root_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = os.path.join(tmpdir, ".env")
            with open(env_file, "w") as f:
                f.write("KNOWLEDGE_CHUNK_SIZE=400\n")

            manager = ConfigurationManager(DotEnvProvider(env_file=env_file))
            with pytest.raises(ConfigurationResolutionFailed):
                manager.resolve(KnowledgeConfiguration)
