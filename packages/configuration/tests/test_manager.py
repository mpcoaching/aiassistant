"""
Tests for the ConfigurationManager.
"""

from __future__ import annotations

import pytest

from configuration.contracts.v1.database import DatabaseConfiguration
from configuration.contracts.v1.message_bus import MessageBusConfiguration
from configuration.manager import ConfigurationManager
from configuration.providers import ConfigurationResolutionFailed


class FakeProvider:
    name = "fake"

    def __init__(self, data: dict[str, str]):
        self._data = data

    def read(self) -> dict[str, str]:
        return dict(self._data)


class TestResolve:
    def test_resolves_model(self):
        provider = FakeProvider({"DATABASE_URL": "postgres://localhost/db"})
        manager = ConfigurationManager(provider)
        result = manager.resolve(DatabaseConfiguration)
        assert result.url == "postgres://localhost/db"

    def test_caches_result(self):
        provider = FakeProvider({"DATABASE_URL": "postgres://localhost/db"})
        manager = ConfigurationManager(provider)
        first = manager.resolve(DatabaseConfiguration)
        second = manager.resolve(DatabaseConfiguration)
        assert first is second

    def test_cache_keyed_by_model_class(self):
        provider = FakeProvider({
            "DATABASE_URL": "postgres://localhost/db",
            "RABBITMQ_URL": "amqp://localhost",
        })
        manager = ConfigurationManager(provider)
        db = manager.resolve(DatabaseConfiguration)
        bus = manager.resolve(MessageBusConfiguration)
        assert db is not bus
        assert db.url == "postgres://localhost/db"
        assert bus.url == "amqp://localhost"

    def test_missing_required_field_raises(self):
        provider = FakeProvider({})
        manager = ConfigurationManager(provider)
        with pytest.raises(ConfigurationResolutionFailed) as exc_info:
            manager.resolve(DatabaseConfiguration)
        assert "DatabaseConfiguration" in str(exc_info.value)

    def test_resolve_returns_frozen_model(self):
        provider = FakeProvider({"DATABASE_URL": "postgres://localhost/db"})
        manager = ConfigurationManager(provider)
        result = manager.resolve(DatabaseConfiguration)
        with pytest.raises(Exception):
            result.url = "mutated"
