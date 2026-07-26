"""Tests for the Platform Bootstrapper."""

from __future__ import annotations

import pytest
from unittest.mock import Mock
from pydantic import BaseModel, ValidationError

from configuration.manager import ConfigurationManager
from configuration.providers import EnvironmentProvider
from capability import Capability, CapabilityContext
from platform.bootstrapper import bootstrap


class TestConfig(BaseModel):
    test_value: str
    required_field: str


class MockLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg: str, **kwargs) -> None:
        self.messages.append(("info", msg, kwargs))

    def error(self, msg: str, **kwargs) -> None:
        self.messages.append(("error", msg, kwargs))

    def warning(self, msg: str, **kwargs) -> None:
        self.messages.append(("warning", msg, kwargs))


class MockEventBus:
    def __init__(self):
        self.published = []

    def publish(self, routing_key: str, payload: dict) -> None:
        self.published.append((routing_key, payload))


class TestCapability:
    """Test capability that implements the Capability protocol."""

    configuration_type = TestConfig

    def __init__(self, context: CapabilityContext) -> None:
        self.context = context
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = False


def test_bootstrap_success() -> None:
    """Test that bootstrap succeeds with valid configuration."""
    # Setup environment
    import os
    os.environ["TEST_VALUE"] = "test"
    os.environ["REQUIRED_FIELD"] = "required"

    try:
        # Setup configuration manager with environment provider
        provider = EnvironmentProvider()
        manager = ConfigurationManager(provider)

        # Create platform services
        logger = MockLogger()
        event_bus = MockEventBus()

        # Bootstrap capability
        capability = bootstrap(TestCapability, manager, logger, event_bus)

        # Verify capability was created and started
        assert isinstance(capability, TestCapability)
        assert capability.started

        # Verify context was properly set
        assert capability.context.configuration.test_value == "test"
        assert capability.context.configuration.required_field == "required"
        assert capability.context.logger is logger
        assert capability.context.event_bus is event_bus

        # Verify capability can be stopped
        capability.stop()
        assert capability.stopped

    finally:
        # Cleanup environment
        os.environ.pop("TEST_VALUE", None)
        os.environ.pop("REQUIRED_FIELD", None)


def test_bootstrap_fails_fast_on_missing_config() -> None:
    """Test that bootstrap fails fast when required configuration is missing."""
    # Setup environment with missing required field
    import os
    os.environ["TEST_VALUE"] = "test"
    # DELIBERATELY NOT SETTING REQUIRED_FIELD

    try:
        # Setup configuration manager with environment provider
        provider = EnvironmentProvider()
        manager = ConfigurationManager(provider)

        # Create platform services
        logger = MockLogger()
        event_bus = MockEventBus()

        # Bootstrap should raise ConfigurationResolutionFailed
        with pytest.raises(Exception):  # ConfigurationResolutionFailed
            bootstrap(TestCapability, manager, logger, event_bus)

    finally:
        # Cleanup environment
        os.environ.pop("TEST_VALUE", None)


def test_bootstrap_uses_dynamic_config_contract() -> None:
    """Test that bootstrap uses the capability's declared configuration_type."""
    # Setup environment
    import os
    os.environ["TEST_VALUE"] = "test"
    os.environ["REQUIRED_FIELD"] = "required"

    try:
        # Setup configuration manager with environment provider
        provider = EnvironmentProvider()
        manager = ConfigurationManager(provider)

        # Create platform services
        logger = MockLogger()
        event_bus = MockEventBus()

        # Bootstrap capability - should use TestConfig from capability_type
        capability = bootstrap(TestCapability, manager, logger, event_bus)

        # Verify it worked with the correct config type
        assert capability.context.configuration.test_value == "test"

    finally:
        # Cleanup environment
        os.environ.pop("TEST_VALUE", None)
        os.environ.pop("REQUIRED_FIELD", None)


def test_bootstrap_constructs_via_constructor_injection() -> None:
    """Test that bootstrap constructs capability via constructor injection."""
    # Setup environment
    import os
    os.environ["TEST_VALUE"] = "test"
    os.environ["REQUIRED_FIELD"] = "required"

    try:
        # Setup configuration manager with environment provider
        provider = EnvironmentProvider()
        manager = ConfigurationManager(provider)

        # Create platform services
        logger = MockLogger()
        event_bus = MockEventBus()

        # Bootstrap capability
        capability = bootstrap(TestCapability, manager, logger, event_bus)

        # Verify the capability received the context via constructor
        assert capability.context is not None
        assert capability.context.configuration is not None
        assert capability.context.logger is logger
        assert capability.context.event_bus is event_bus

    finally:
        # Cleanup environment
        os.environ.pop("TEST_VALUE", None)
        os.environ.pop("REQUIRED_FIELD", None)