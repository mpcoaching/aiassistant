"""Tests for the Capability protocol and CapabilityContext."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from capability import CapabilityContext
from pydantic import BaseModel


class DummyConfig(BaseModel):
    value: str


class DummyLogger:
    def info(self, msg: str, **kwargs) -> None:
        pass

    def error(self, msg: str, **kwargs) -> None:
        pass

    def warning(self, msg: str, **kwargs) -> None:
        pass


class DummyEventBus:
    def publish(self, routing_key: str, payload: dict) -> None:
        pass


class DummyCapability:
    """Minimal capability implementing the Capability protocol."""

    configuration_type = DummyConfig

    def __init__(self, context: CapabilityContext) -> None:
        self.context = context
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_capability_protocol_accepts_context() -> None:
    """A capability implementing the protocol can be constructed with CapabilityContext."""
    context = CapabilityContext(
        configuration=DummyConfig(value="test"),
        logger=DummyLogger(),
        event_bus=DummyEventBus(),
    )
    cap = DummyCapability(context=context)
    assert cap.context is context


def test_capability_context_is_immutable() -> None:
    """CapabilityContext is frozen and cannot be modified after creation."""
    context = CapabilityContext(
        configuration=DummyConfig(value="test"),
        logger=DummyLogger(),
        event_bus=DummyEventBus(),
    )

    with pytest.raises(FrozenInstanceError, match="cannot assign to field"):
        context.configuration = DummyConfig(value="modified")


def test_capability_lifecycle() -> None:
    """Capability start/stop lifecycle works correctly."""
    context = CapabilityContext(
        configuration=DummyConfig(value="test"),
        logger=DummyLogger(),
        event_bus=DummyEventBus(),
    )
    cap = DummyCapability(context=context)

    assert not cap.started
    assert not cap.stopped

    cap.start()
    assert cap.started

    cap.stop()
    assert cap.stopped


def test_capability_owns_configuration_contract() -> None:
    """Capability declares its configuration contract via configuration_type attribute."""
    assert DummyCapability.configuration_type is DummyConfig


def test_capability_context_carries_all_dependencies() -> None:
    """CapabilityContext carries configuration, logger, and event_bus."""
    config = DummyConfig(value="test")
    logger = DummyLogger()
    bus = DummyEventBus()

    context = CapabilityContext(
        configuration=config,
        logger=logger,
        event_bus=bus,
    )

    assert context.configuration is config
    assert context.logger is logger
    assert context.event_bus is bus
