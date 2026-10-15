"""
Capability Protocol

Defines the contract that all platform-hosted capabilities must implement.
Capabilities receive dependencies via constructor injection of CapabilityContext.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pydantic import BaseModel

    from capability import CapabilityContext


class Capability(Protocol):
    """Protocol for platform-hosted capabilities.

    A capability MUST:
    - Declare its configuration contract via the `configuration_type` class attribute
    - Accept a `CapabilityContext` instance via constructor injection
    - Implement `start()` and `stop()` lifecycle methods

    A capability MUST NOT:
    - Create ConfigurationManager
    - Select configuration providers
    - Read environment variables directly
    - Load .env files
    - Initialize infrastructure services (logger, event bus, etc.)
    """

    configuration_type: type[BaseModel]

    def __init__(self, context: CapabilityContext) -> None:
        """Initialize capability with injected context.

        Args:
            context: Immutable context containing configuration, logger, and event bus.
        """
        ...

    def start(self) -> None:
        """Start the capability. Called once after construction."""
        ...

    def stop(self) -> None:
        """Stop the capability. Called during platform shutdown."""
        ...
