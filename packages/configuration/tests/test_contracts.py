"""
Tests for configuration contracts.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from configuration.contracts.base import Contract, Lifecycle
from configuration.contracts.v1.database import DatabaseConfiguration
from configuration.contracts.v1.langgraph_runtime import LangGraphRuntimeConfiguration
from configuration.contracts.v1.message_bus import MessageBusConfiguration


class TestLifecycle:
    def test_creates_lifecycle(self):
        lc = Lifecycle(platform="platform", capability="database", execution="runtime")
        assert lc.platform == "platform"
        assert lc.capability == "database"
        assert lc.execution == "runtime"

    def test_lifecycle_is_frozen(self):
        lc = Lifecycle(platform="platform", capability="database", execution="runtime")
        with pytest.raises(ValidationError):
            lc.platform = "other"


class TestContractMetadata:
    def test_database_type_id(self):
        assert DatabaseConfiguration.type_id() == "database"

    def test_database_purpose(self):
        assert DatabaseConfiguration.purpose() == "Database connection configuration"

    def test_database_owner(self):
        assert DatabaseConfiguration.owner() == "platform"

    def test_database_lifecycle(self):
        lc = DatabaseConfiguration.lifecycle()
        assert lc.platform == "platform"
        assert lc.capability == "database"
        assert lc.execution == "runtime"

    def test_database_documentation(self):
        assert DatabaseConfiguration.documentation() == "Configuration for connecting to the PostgreSQL database"

    def test_database_validation_strategy_returns_none_by_default(self):
        assert DatabaseConfiguration.validation_strategy() is None

    def test_message_bus_type_id(self):
        assert MessageBusConfiguration.type_id() == "message-bus"

    def test_message_bus_purpose(self):
        assert MessageBusConfiguration.purpose() == "Message bus connection configuration"

    def test_message_bus_owner(self):
        assert MessageBusConfiguration.owner() == "platform"

    def test_message_bus_lifecycle(self):
        lc = MessageBusConfiguration.lifecycle()
        assert lc.platform == "platform"
        assert lc.capability == "message-bus"
        assert lc.execution == "runtime"

    def test_langgraph_type_id(self):
        assert LangGraphRuntimeConfiguration.type_id() == "langgraph-runtime"

    def test_langgraph_purpose(self):
        assert LangGraphRuntimeConfiguration.purpose() == "LangGraph runtime connection configuration"

    def test_langgraph_owner(self):
        assert LangGraphRuntimeConfiguration.owner() == "platform"

    def test_langgraph_lifecycle(self):
        lc = LangGraphRuntimeConfiguration.lifecycle()
        assert lc.platform == "platform"
        assert lc.capability == "langgraph"
        assert lc.execution == "runtime"

    def test_contract_is_abstract(self):
        with pytest.raises(TypeError):
            Contract()


class TestDatabaseConfiguration:
    def test_required_url_alias(self):
        cfg = DatabaseConfiguration.model_validate({"DATABASE_URL": "postgres://localhost/db"})
        assert cfg.url == "postgres://localhost/db"

    def test_defaults(self):
        cfg = DatabaseConfiguration.model_validate({"DATABASE_URL": "postgres://localhost/db"})
        assert cfg.pool_size == 5
        assert cfg.max_overflow == 10

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError):
            DatabaseConfiguration.model_validate({})

    def test_override_defaults(self):
        cfg = DatabaseConfiguration.model_validate({
            "DATABASE_URL": "postgres://localhost/db",
            "DATABASE_POOL_SIZE": "10",
            "DATABASE_MAX_OVERFLOW": "20",
        })
        assert cfg.pool_size == 10
        assert cfg.max_overflow == 20

    def test_immutable(self):
        cfg = DatabaseConfiguration.model_validate({"DATABASE_URL": "postgres://localhost/db"})
        with pytest.raises(ValidationError):
            cfg.url = "new://url"


class TestMessageBusConfiguration:
    def test_required_url_alias(self):
        cfg = MessageBusConfiguration.model_validate({"RABBITMQ_URL": "amqp://localhost"})
        assert cfg.url == "amqp://localhost"

    def test_default_fallback_dir(self):
        cfg = MessageBusConfiguration.model_validate({"RABBITMQ_URL": "amqp://localhost"})
        assert cfg.fallback_dir == "/aiassistant/.events"

    def test_override_fallback_dir(self):
        cfg = MessageBusConfiguration.model_validate({
            "RABBITMQ_URL": "amqp://localhost",
            "EVENTS_FALLBACK_DIR": "/tmp/events",
        })
        assert cfg.fallback_dir == "/tmp/events"

    def test_default_url(self):
        cfg = MessageBusConfiguration.model_validate({})
        assert cfg.url == "amqp://guest:guest@rabbitmq:5672/"

    def test_override_url(self):
        cfg = MessageBusConfiguration.model_validate({"RABBITMQ_URL": "amqp://custom"})
        assert cfg.url == "amqp://custom"


class TestLangGraphRuntimeConfiguration:
    def test_defaults(self):
        cfg = LangGraphRuntimeConfiguration.model_validate({})
        assert cfg.url == "http://langgraph:8000"
        assert cfg.timeout_seconds == 300.0
        assert cfg.retries == 3

    def test_override_via_alias(self):
        cfg = LangGraphRuntimeConfiguration.model_validate({
            "LANGGRAPH_URL": "http://custom:9000",
            "LANGGRAPH_TIMEOUT": "60.0",
            "LANGGRAPH_RETRIES": "5",
        })
        assert cfg.url == "http://custom:9000"
        assert cfg.timeout_seconds == 60.0
        assert cfg.retries == 5

    def test_immutable(self):
        cfg = LangGraphRuntimeConfiguration.model_validate({})
        with pytest.raises(ValidationError):
            cfg.url = "new://url"
