"""
Database Configuration Contract.

Defines the configuration required to connect to the database.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DatabaseConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    url: str = Field(validation_alias="DATABASE_URL")
    pool_size: int = Field(default=5, validation_alias="DATABASE_POOL_SIZE")
    max_overflow: int = Field(default=10, validation_alias="DATABASE_MAX_OVERFLOW")
