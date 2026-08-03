"""
Capability Context

Immutable boundary carrying platform-provided dependencies to capabilities.
This is the only way capabilities receive platform dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import Logger

    from bus import EventBus
    from pydantic import BaseModel


@dataclass(frozen=True)
class CapabilityContext:
    """Immutable context injected into capabilities at construction time.

    Contains exactly the three platform-owned dependencies that capabilities require:
    - Resolved configuration (specific to each capability's configuration_type)
    - Platform logger for structured logging
    - Platform event bus for inter-service communication

    Capabilities MUST NOT access any other platform services or attempt to resolve
    configuration themselves. All dependencies flow through this context.
    """

    configuration: BaseModel
    logger: Logger
    event_bus: EventBus

    # Note: Logger and EventBus types are imported conditionally below
    # to avoid circular imports during type checking