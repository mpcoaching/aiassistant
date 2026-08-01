"""
Database Configuration Contract.

Defines the configuration required to connect to the database.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from configuration.contracts.base import Contract, Lifecycle


class DatabaseConfiguration(Contract, BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    url: str = Field(validation_alias="DATABASE_URL")
    pool_size: int = Field(default=5, validation_alias="DATABASE_POOL_SIZE")
    max_overflow: int = Field(default=10, validation_alias="DATABASE_MAX_OVERFLOW")

    @classmethod
    def type_id(cls) -> str:
        return "database"

    @classmethod
    def purpose(cls) -> str:
        return "Database connection configuration"

    @classmethod
    def owner(cls) -> str:
        return "platform"

    @classmethod
    def lifecycle(cls) -> Lifecycle:
        return Lifecycle(platform="platform", capability="database", execution="runtime")

    @classmethod
    def documentation(cls) -> str:
        return "Configuration for connecting to the PostgreSQL database"
