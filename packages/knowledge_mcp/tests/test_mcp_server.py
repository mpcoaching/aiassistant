"""
Tests for the knowledge-mcp MCP server (Phase 1 skeleton).
"""

from __future__ import annotations

import pytest

from knowledge_mcp.mcp_server import mcp


class TestMcpServer:
    def test_server_name(self):
        assert mcp.name == "knowledge_mcp"

    @pytest.mark.asyncio
    async def test_tools_list_empty(self):
        tools = await mcp.list_tools()
        assert isinstance(tools, list)
        assert len(tools) == 0
