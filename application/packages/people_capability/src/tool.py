"""
People/Capability domain — Tool model (Increment 28).

A Tool is an executable resource that can support an Actor, Skill,
Capability, or Workflow.

The Tool model describes a tool independently of its implementation. The
implementation could be Python, MCP, an HTTP API, Paperclip, LangGraph, or
another service — but the organisational model never requires Paperclip.

Imports: pydantic, standard library only. No organisation, no Paperclip, no LangGraph.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ToolImplementationType(str, Enum):
    """How a Tool is executed — never a Paperclip/MCP/LangGraph model.

    These values describe the *mechanism*, not the implementation details.
    Adapters in the execution layer map these to concrete runtimes.
    """

    PYTHON = "python"
    MCP = "mcp"
    HTTP_API = "http_api"
    PAPERCLIP = "paperclip"
    LANGGRAPH = "langgraph"
    EXTERNAL_SERVICE = "external_service"


class Tool(BaseModel):
    """An executable resource that supports Actors, Skills, Capabilities, or Workflows.

    The Tool is an organisational concept: it describes *what* the tool does
    and *how* it is implemented, without coupling to any specific runtime.

    The ``implementation_ref`` field carries a lightweight reference that the
    execution adapter resolves — e.g. an MCP server name, a Python module path,
    a Paperclip agent ID, or an HTTP endpoint URL.
    """

    id: str
    name: str
    description: str = ""
    implementation_type: ToolImplementationType = ToolImplementationType.PYTHON
    implementation_ref: str | None = Field(
        default=None,
        description="Reference resolved by the execution adapter (module path, MCP name, agent ID, URL, etc.)",
    )
    supports: list[str] = Field(
        default_factory=list,
        description="IDs of Capabilities/Skills this Tool supports",
    )
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
