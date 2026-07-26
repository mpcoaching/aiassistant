"""
LangGraph Runtime Configuration Contract.

Defines the configuration required to connect to the LangGraph runtime.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LangGraphRuntimeConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    url: str = Field(default="http://langgraph:8000", validation_alias="LANGGRAPH_URL")
    timeout_seconds: float = Field(default=300.0, validation_alias="LANGGRAPH_TIMEOUT")
    retries: int = Field(default=3, validation_alias="LANGGRAPH_RETRIES")
