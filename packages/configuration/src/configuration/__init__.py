"""
Configuration Manager capability — contract-based, provider-driven configuration resolution.
"""

from __future__ import annotations

from configuration.contracts import (
    DatabaseConfiguration,
    LangGraphRuntimeConfiguration,
    MessageBusConfiguration,
)
from configuration.manager import ConfigurationManager
from configuration.providers import (
    ConfigurationProvider,
    ConfigurationResolutionFailed,
    ProviderUnavailableError,
)
from configuration.providers.dotenv import DotEnvProvider

__all__ = [
    "ConfigurationManager",
    "ConfigurationProvider",
    "ConfigurationResolutionFailed",
    "DatabaseConfiguration",
    "DotEnvProvider",
    "LangGraphRuntimeConfiguration",
    "MessageBusConfiguration",
    "ProviderUnavailableError",
]
