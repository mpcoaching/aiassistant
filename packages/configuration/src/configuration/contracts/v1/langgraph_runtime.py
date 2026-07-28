"""
LangGraph Runtime Configuration Contract.

Defines the configuration required to connect to the LangGraph runtime.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from configuration.contracts.base import Contract, Lifecycle


class LangGraphRuntimeConfiguration(Contract, BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    url: str = Field(default="http://langgraph:8000", validation_alias="LANGGRAPH_URL")
    timeout_seconds: float = Field(default=300.0, validation_alias="LANGGRAPH_TIMEOUT")
    retries: int = Field(default=3, validation_alias="LANGGRAPH_RETRIES")

    @classmethod
    def type_id(cls) -> str:
        return "langgraph-runtime"

    @classmethod
    def purpose(cls) -> str:
        return "LangGraph runtime connection configuration"

    @classmethod
    def owner(cls) -> str:
        return "platform"

    @classmethod
    def lifecycle(cls) -> Lifecycle:
        return Lifecycle(platform="platform", capability="langgraph", execution="runtime")

    @classmethod
    def documentation(cls) -> str:
        return "Configuration for connecting to the LangGraph runtime"
