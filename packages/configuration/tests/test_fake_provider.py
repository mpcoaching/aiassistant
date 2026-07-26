"""
Tests proving provider substitution works.
The test must not instantiate DotEnvProvider.
"""

from __future__ import annotations

from configuration.contracts.v1.database import DatabaseConfiguration
from configuration.contracts.v1.langgraph_runtime import LangGraphRuntimeConfiguration
from configuration.contracts.v1.message_bus import MessageBusConfiguration
from configuration.manager import ConfigurationManager
from configuration.providers import ConfigurationProvider


class FakeProvider(ConfigurationProvider):
    name = "fake"

    def __init__(self, data: dict[str, str]):
        self._data = data

    def read(self) -> dict[str, str]:
        return dict(self._data)


class TestFakeProviderSubstitution:
    def test_resolves_all_contracts_with_fake_provider(self):
        data = {
            "RABBITMQ_URL": "amqp://fake-rabbit",
            "EVENTS_FALLBACK_DIR": "/tmp/fake-events",
            "DATABASE_URL": "postgres://fake-db",
            "DATABASE_POOL_SIZE": "2",
            "DATABASE_MAX_OVERFLOW": "4",
            "LANGGRAPH_URL": "http://fake-langgraph",
            "LANGGRAPH_TIMEOUT": "60.0",
            "LANGGRAPH_RETRIES": "2",
        }
        provider = FakeProvider(data)
        manager = ConfigurationManager(provider)

        bus = manager.resolve(MessageBusConfiguration)
        assert bus.url == "amqp://fake-rabbit"
        assert bus.fallback_dir == "/tmp/fake-events"

        db = manager.resolve(DatabaseConfiguration)
        assert db.url == "postgres://fake-db"
        assert db.pool_size == 2
        assert db.max_overflow == 4

        lang = manager.resolve(LangGraphRuntimeConfiguration)
        assert lang.url == "http://fake-langgraph"
        assert lang.timeout_seconds == 60.0
        assert lang.retries == 2
