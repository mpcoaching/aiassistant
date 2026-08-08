"""
Qdrant Configuration Contract.

Defines the configuration required to connect to the Qdrant vector store.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from configuration.contracts.base import Contract, Lifecycle


class QdrantConfiguration(Contract, BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    url: str = Field(default="https://qdrant.local.test", validation_alias="QDRANT_URL")
    api_key: str = Field(
        validation_alias=AliasChoices("QDRANT_API_KEY", "QDRANT_KEY")
    )

    @classmethod
    def type_id(cls) -> str:
        return "qdrant"

    @classmethod
    def purpose(cls) -> str:
        return "Qdrant vector store connection configuration"

    @classmethod
    def owner(cls) -> str:
        return "platform"

    @classmethod
    def lifecycle(cls) -> Lifecycle:
        return Lifecycle(platform="platform", capability="qdrant", execution="runtime")

    @classmethod
    def documentation(cls) -> str:
        return "Configuration for connecting to the Qdrant vector store"
