"""
Configuration Manager capability — contract-based, provider-driven configuration resolution.
"""

from __future__ import annotations

from configuration.contracts import (
    Contract,
    DatabaseConfiguration,
    LangGraphRuntimeConfiguration,
    Lifecycle,
    MessageBusConfiguration,
    RegistryConfiguration,
)
from configuration.manager import ConfigurationManager
from configuration.providers import (
    ConfigurationProvider,
    ConfigurationResolutionFailed,
    ProviderUnavailableError,
    RegistryProvider,
    RegistryValidationResult,
)
from configuration.providers.dotenv import DotEnvProvider

__all__ = [
    "ConfigurationManager",
    "ConfigurationProvider",
    "ConfigurationResolutionFailed",
    "Contract",
    "DatabaseConfiguration",
    "DotEnvProvider",
    "LangGraphRuntimeConfiguration",
    "Lifecycle",
    "MessageBusConfiguration",
    "ProviderUnavailableError",
    "RegistryConfiguration",
    "RegistryProvider",
    "RegistryValidationResult",
]
