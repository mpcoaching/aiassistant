"""
Message Bus Configuration Contract.

Defines the configuration required to connect to the message bus.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MessageBusConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    url: str = Field(default="amqp://guest:guest@rabbitmq:5672/", validation_alias="RABBITMQ_URL")
    fallback_dir: str = Field(default="/aiassistant/.events", validation_alias="EVENTS_FALLBACK_DIR")
