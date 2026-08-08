"""
Minimal Knowledge MCP Server (Phase 1 skeleton).

Provides an empty MCP server that responds to initialize and tools/list.
Retrieval tools will be added in later phases.
"""

from __future__ import annotations

import logging
import sys

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

    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
