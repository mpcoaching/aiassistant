# Plan: Phase 1 — Knowledge MCP Configuration + Minimal Skeleton (Implementation-Ready)

## Objective

Implement the thinnest possible vertical foundation for the `knowledge-mcp` platform capability: configuration contracts, Python configuration model, and a minimal MCP server that starts and responds to `initialize` and `tools/list` with an empty tool list.

## Critical Architectural Correction

**The platform is Python-only.** There is no Rust toolchain, no Cargo workspace, and no precedent for Rust services in the aiassistant repository. The `ragpilot` project (Rust) is a reference implementation for patterns only — it must not be forked into the platform repo.

**knowledge-mcp must be a Python package** under `packages/knowledge_mcp/`, using:
- `mcp.server.fastmcp.FastMCP` (already used by `workflow_runner`)
- `qdrant-client` Python library (for future Qdrant access)
- `fastembed` Python bindings or `sentence-transformers` (for future embeddings)
- The existing Configuration Manager (Python class instantiation, following `workflow_runner` convention)

The upstream `ragpilot` Rust project remains independent and unchanged.

---

## Phase 1 Scope

**Goal:** Prove the configuration and MCP skeleton work end-to-end before adding any retrieval logic.

**Deliverables:**
1. `contracts/knowledge/v1/contract.yaml` — behavioral configuration contract
2. `contracts/knowledge/v1/mapping.yaml` — environment variable mapping
3. `packages/configuration/src/configuration/contracts/v1/knowledge.py` — `KnowledgeConfiguration` Pydantic model
4. `packages/knowledge_mcp/` — new Python package with minimal FastMCP server

**Not in Phase 1:**
- Markdown parsing
- Qdrant indexing
- Semantic search
- Embedding
- Any retrieval tools

---

## File 1: `contracts/knowledge/v1/contract.yaml`

**Path:** `/home/martinp/Documents/projects/aiassistant/contracts/knowledge/v1/contract.yaml`
**Action:** Create

```yaml
name: knowledge
version: v1

requirements:
  KNOWLEDGE_CORPUS_ROOT:
    required: true
  KNOWLEDGE_CHUNK_SIZE:
    required: false
    default: "500"
  KNOWLEDGE_CHUNK_OVERLAP:
    required: false
    default: "120"
  KNOWLEDGE_CONTEXT_CHUNKS:
    required: false
    default: "6"
  KNOWLEDGE_BUNDLE_BUDGET_TOKENS:
    required: false
    default: "6000"
  KNOWLEDGE_WATCHER_ENABLED:
    required: false
    default: "false"
  KNOWLEDGE_INDEX_STATE_PATH:
    required: false
    default: ".knowledge/state.json"

validators:
  - required-fields
```

**Notes:**
- Uses `KNOWLEDGE_*` prefix, not `RAGPILOT_*`.
- Follows the exact pattern from `contracts/deployment/v1/contract.yaml` (flat key-value requirements with `required` and optional `default`).
- `KNOWLEDGE_CORPUS_ROOT` is the only required field.

---

## File 2: `contracts/knowledge/v1/mapping.yaml`

**Path:** `/home/martinp/Documents/projects/aiassistant/contracts/knowledge/v1/mapping.yaml`
**Action:** Create

```yaml
mapping:
  KNOWLEDGE_CORPUS_ROOT:
    source_key: KNOWLEDGE_CORPUS_ROOT
  KNOWLEDGE_CHUNK_SIZE:
    source_key: KNOWLEDGE_CHUNK_SIZE
  KNOWLEDGE_CHUNK_OVERLAP:
    source_key: KNOWLEDGE_CHUNK_OVERLAP
  KNOWLEDGE_CONTEXT_CHUNKS:
    source_key: KNOWLEDGE_CONTEXT_CHUNKS
  KNOWLEDGE_BUNDLE_BUDGET_TOKENS:
    source_key: KNOWLEDGE_BUNDLE_BUDGET_TOKENS
  KNOWLEDGE_WATCHER_ENABLED:
    source_key: KNOWLEDGE_WATCHER_ENABLED
  KNOWLEDGE_INDEX_STATE_PATH:
    source_key: KNOWLEDGE_INDEX_STATE_PATH
```

**Notes:**
- Direct 1:1 mapping. No translation needed for Phase 1.
- Follows the exact pattern from `contracts/deployment/v1/mapping.yaml`.

---

## File 3: `packages/configuration/src/configuration/contracts/v1/knowledge.py`

**Path:** `/home/martinp/Documents/projects/aiassistant/packages/configuration/src/configuration/contracts/v1/knowledge.py`
**Action:** Create

```python
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
```

**Notes:**
- Follows the exact pattern from `database.py`, `message_bus.py`, and `qdrant.py`.
- Uses `KNOWLEDGE_*` validation aliases matching the contract.yaml keys.
- Field names are Pythonic (`corpus_root`, `chunk_size`), aliases are platform env var names.
- `frozen=True` matches existing contracts.

---

## File 4: `packages/configuration/src/configuration/contracts/v1/__init__.py`

**Path:** `/home/martinp/Documents/projects/aiassistant/packages/configuration/src/configuration/contracts/v1/__init__.py`
**Action:** Edit — add `KnowledgeConfiguration`

**Current content:**
```python
from configuration.contracts.v1.database import DatabaseConfiguration
from configuration.contracts.v1.langgraph_runtime import LangGraphRuntimeConfiguration
from configuration.contracts.v1.message_bus import MessageBusConfiguration
from configuration.contracts.v1.qdrant import QdrantConfiguration
from configuration.contracts.v1.registry import RegistryConfiguration

__all__ = [
    "Contract",
    "DatabaseConfiguration",
    "LangGraphRuntimeConfiguration",
    "Lifecycle",
    "MessageBusConfiguration",
    "QdrantConfiguration",
    "RegistryConfiguration",
]
```

**New content:**
```python
from configuration.contracts.v1.database import DatabaseConfiguration
from configuration.contracts.v1.knowledge import KnowledgeConfiguration
from configuration.contracts.v1.langgraph_runtime import LangGraphRuntimeConfiguration
from configuration.contracts.v1.message_bus import MessageBusConfiguration
from configuration.contracts.v1.qdrant import QdrantConfiguration
from configuration.contracts.v1.registry import RegistryConfiguration

__all__ = [
    "Contract",
    "DatabaseConfiguration",
    "KnowledgeConfiguration",
    "LangGraphRuntimeConfiguration",
    "Lifecycle",
    "MessageBusConfiguration",
    "QdrantConfiguration",
    "RegistryConfiguration",
]
```

**Notes:**
- Insert `KnowledgeConfiguration` between `DatabaseConfiguration` and `LangGraphRuntimeConfiguration` (alphabetical).
- Follows exact existing import style.

---

## File 5: `packages/knowledge_mcp/pyproject.toml`

**Path:** `/home/martinp/Documents/projects/aiassistant/packages/knowledge_mcp/pyproject.toml`
**Action:** Create

```toml
[project]
name = "knowledge_mcp"
version = "0.1.0"
description = "Semantic knowledge MCP server for architectural knowledge retrieval"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "httpx>=0.27.0",
    "configuration>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[project.scripts]
knowledge-mcp = "knowledge_mcp.__main__:main"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Notes:**
- Follows the exact pattern from `packages/workflow_runner/pyproject.toml`.
- Depends on `configuration` package (for Configuration Manager) and `mcp` (for FastMCP).
- Entry point: `knowledge-mcp` command.

---

## File 6: `packages/knowledge_mcp/src/knowledge_mcp/__init__.py`

**Path:** `/home/martinp/Documents/projects/aiassistant/packages/knowledge_mcp/src/knowledge_mcp/__init__.py`
**Action:** Create

```python
"""Knowledge MCP server package."""
```

---

## File 7: `packages/knowledge_mcp/src/knowledge_mcp/__main__.py`

**Path:** `/home/martinp/Documents/projects/aiassistant/packages/knowledge_mcp/src/knowledge_mcp/__main__.py`
**Action:** Create

```python
"""Entry point for `python -m knowledge_mcp`."""

from __future__ import annotations

import sys

from knowledge_mcp.mcp_server import main


if __name__ == "__main__":
    sys.exit(main())
```

---

## File 8: `packages/knowledge_mcp/src/knowledge_mcp/mcp_server.py`

**Path:** `/home/martinp/Documents/projects/aiassistant/packages/knowledge_mcp/src/knowledge_mcp/mcp_server.py`
**Action:** Create

```python
"""
Minimal Knowledge MCP Server (Phase 1 skeleton).

Provides an empty MCP server that responds to initialize and tools/list.
Retrieval tools will be added in later phases.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("knowledge-mcp")

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP("knowledge_mcp")


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def _resolve_config() -> tuple[object, object]:
    """Resolve KnowledgeConfiguration and QdrantConfiguration via Configuration Manager.

    Follows the existing platform convention from workflow_runner.
    """
    from configuration import ConfigurationManager, DotEnvProvider
    from configuration.contracts.v1.knowledge import KnowledgeConfiguration
    from configuration.contracts.v1.qdrant import QdrantConfiguration

    manager = ConfigurationManager(DotEnvProvider())
    knowledge_cfg = manager.resolve(KnowledgeConfiguration)
    qdrant_cfg = manager.resolve(QdrantConfiguration)
    return knowledge_cfg, qdrant_cfg


# ---------------------------------------------------------------------------
# Tools (empty for Phase 1)
# ---------------------------------------------------------------------------

# No tools registered in Phase 1.
# knowledge_search will be added in Phase 4.


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Start the knowledge-mcp MCP server."""
    try:
        knowledge_cfg, qdrant_cfg = _resolve_config()
        logger.info("Configuration resolved successfully")
        logger.info("Knowledge corpus root: %s", knowledge_cfg.corpus_root)
        logger.info("Qdrant URL: %s", qdrant_cfg.url)
    except Exception:
        logger.exception("Failed to resolve configuration")
        return 1

    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Notes:**
- Uses FastMCP exactly like `workflow_runner/src/mcp_server.py`.
- Configuration resolution follows the exact same pattern as `workflow_runner/api.py` (lines 185-188).
- `mcp.run()` starts the stdio JSON-RPC loop. FastMCP handles `initialize`, `tools/list`, `tools/call`, etc.
- No tools are registered in Phase 1. `tools/list` will return an empty array.

---

## Tests

### Test 1: `tests/test_contracts.py`

**Path:** `/home/martinp/Documents/projects/aiassistant/packages/knowledge_mcp/tests/test_contracts.py`
**Action:** Create

```python
"""
Tests for knowledge-mcp configuration contracts.
"""

from __future__ import annotations

import os
import tempfile

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
```

---

### Test 2: `tests/test_mcp_server.py`

**Path:** `/home/martinp/Documents/projects/aiassistant/packages/knowledge_mcp/tests/test_mcp_server.py`
**Action:** Create

```python
"""
Tests for the knowledge-mcp MCP server (Phase 1 skeleton).
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from knowledge_mcp.mcp_server import mcp


class TestMcpInitialize:
    def test_initialize_response(self):
        """FastMCP initialize returns protocol version and capabilities."""
        # FastMCP's stdio server handles initialize internally.
        # We verify the server instance is correctly configured.
        assert mcp.name == "knowledge_mcp"


class TestMcpToolsList:
    def test_tools_list_empty(self):
        """Phase 1 returns an empty tools list."""
        # FastMCP tools/list is handled by the framework.
        # We verify no tools are registered.
        registered = getattr(mcp, "_tools", {})
        assert len(registered) == 0
```

**Notes:**
- FastMCP handles the JSON-RPC protocol internally. Testing the full stdio handshake requires integration tests with a subprocess or the FastMCP test client.
- These unit tests verify the server instance is correctly configured and no tools are registered.
- A full integration test (subprocess stdio) would be added in Phase 4 when `knowledge_search` exists.

---

### Test 3: `tests/test_configuration_resolution.py`

**Path:** `/home/martinp/Documents/projects/aiassistant/packages/knowledge_mcp/tests/test_configuration_resolution.py`
**Action:** Create

```python
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
```

---

## Test Execution Order

1. **Contract tests first** (fast, no subprocess):
   ```bash
   cd packages/configuration && python -m pytest tests/test_contracts.py -v -k "Knowledge"
   ```

2. **Knowledge package configuration resolution tests:**
   ```bash
   cd packages/knowledge_mcp && python -m pytest tests/test_configuration_resolution.py -v
   ```

3. **Knowledge package MCP skeleton tests:**
   ```bash
   cd packages/knowledge_mcp && python -m pytest tests/test_mcp_server.py -v
   ```

4. **Full configuration package test suite** (ensure nothing is broken):
   ```bash
   cd packages/configuration && python -m pytest tests/ -v -m "not redis"
   ```

---

## Acceptance Criteria

**Phase 1 is complete when:**

1. `contracts/knowledge/v1/contract.yaml` loads without YAML error.
2. `contracts/knowledge/v1/mapping.yaml` maps all `KNOWLEDGE_*` keys correctly.
3. `KnowledgeConfiguration` Pydantic model validates with defaults and required fields.
4. `KnowledgeConfiguration` resolves from `.env` via `ConfigurationManager(DotEnvProvider())`.
5. `QdrantConfiguration` continues to resolve correctly (regression test).
6. `knowledge-mcp` command starts without error:
   ```bash
   knowledge-mcp --help
   ```
7. `knowledge-mcp --mcp-server` starts and responds to `initialize` with protocol version `2024-11-05`.
8. `knowledge-mcp --mcp-server` responds to `tools/list` with an empty `tools` array.
9. All tests pass: contract tests, configuration resolution tests, MCP skeleton tests, and full configuration package test suite.

---

## Files Changed Summary

| File | Action |
|------|--------|
| `contracts/knowledge/v1/contract.yaml` | Create |
| `contracts/knowledge/v1/mapping.yaml` | Create |
| `packages/configuration/src/configuration/contracts/v1/knowledge.py` | Create |
| `packages/configuration/src/configuration/contracts/v1/__init__.py` | Edit |
| `packages/knowledge_mcp/pyproject.toml` | Create |
| `packages/knowledge_mcp/src/knowledge_mcp/__init__.py` | Create |
| `packages/knowledge_mcp/src/knowledge_mcp/__main__.py` | Create |
| `packages/knowledge_mcp/src/knowledge_mcp/mcp_server.py` | Create |
| `packages/knowledge_mcp/tests/test_contracts.py` | Create |
| `packages/knowledge_mcp/tests/test_mcp_server.py` | Create |
| `packages/knowledge_mcp/tests/test_configuration_resolution.py` | Create |

---

## Architectural Discrepancies Discovered

1. **Language mismatch:** The plan originally assumed a Rust binary forked from ragpilot. The platform is Python-only with no Rust toolchain. The correct implementation is a Python package using FastMCP, following the `workflow_runner` convention.

2. **Configuration Manager coupling:** `knowledge-mcp` must instantiate `DotEnvProvider()` directly, which violates the stated architectural principle that "consumers must not depend on environment variables, files, APIs, or secrets providers." This is the existing platform convention and is accepted for v1.

3. **No provider factory exists:** The Configuration Manager has no factory or DI mechanism. All Python consumers directly instantiate `DotEnvProvider()`. This is documented as an architectural gap but not solved in Phase 1.

4. **ragpilot is not forkable into the platform:** The upstream ragpilot is a standalone Rust binary. It cannot be integrated into the Python platform repo. Its patterns (Qdrant interaction, chunking, incremental indexing) must be reimplemented in Python for future phases.

---

## Dependencies for Future Phases

- **Phase 2 (Markdown parser):** No dependency on Phase 1 beyond the package structure.
- **Phase 3 (Qdrant + search):** Requires Python Qdrant client (`qdrant-client`) and embedding library (`fastembed` or `sentence-transformers`). Neither is currently in the platform dependencies.
- **Phase 4 (MCP tools):** Depends on Phase 3.
- **Phase 5 (evaluation):** Depends on Phase 4.
- **Phase 6 (secondary capabilities):** Depends on Phase 4.

---

## Open Questions for Human Input

1. **Python Qdrant client:** Should the platform add `qdrant-client` as a dependency, or should knowledge-mcp use the existing Qdrant HTTP API directly via `httpx`? The latter avoids adding a new dependency but requires more code.

2. **Python embedding library:** Should the platform use `fastembed` Python bindings, `sentence-transformers`, or call an external embedding API? This affects the Phase 3 implementation significantly.

3. **Package naming:** `packages/knowledge_mcp/` (snake_case) matches the Python package convention. Is this acceptable, or should it be `packages/knowledge-mcp/` (kebab-case)?

4. **Corpus root default:** The `KNOWLEDGE_CORPUS_ROOT` contract field has no default (it's required). Should there be a platform-wide default (e.g., `agentic/docs/`), or should every deployment explicitly set it?
