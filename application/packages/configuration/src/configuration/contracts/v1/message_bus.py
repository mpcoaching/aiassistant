"""
Message Bus Configuration Contract.

Defines the configuration required to connect to the message bus.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from configuration.contracts.base import Contract, Lifecycle


class MessageBusConfiguration(Contract, BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    url: str = Field(default="amqp://guest:guest@rabbitmq:5672/", validation_alias="RABBITMQ_URL")
    fallback_dir: str = Field(default="/aiassistant/.events", validation_alias="EVENTS_FALLBACK_DIR")

    @classmethod
    def type_id(cls) -> str:
        return "message-bus"

    @classmethod
    def purpose(cls) -> str:
        return "Message bus connection configuration"

    @classmethod
    def owner(cls) -> str:
        return "platform"

    @classmethod
    def lifecycle(cls) -> Lifecycle:
        return Lifecycle(platform="platform", capability="message-bus", execution="runtime")

    @classmethod
    def documentation(cls) -> str:
        return "Configuration for connecting to the RabbitMQ message bus"
