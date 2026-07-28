"""
Configuration Providers

Providers are adapters that translate external configuration sources into
internal configuration contracts. Consumers never interact with providers
directly — the Configuration Manager selects and orchestrates them.
"""

from __future__ import annotations

from configuration.providers.exceptions import (
    ConfigurationResolutionFailed,
    ProviderUnavailableError,
    RegistryValidationResult,
)
from configuration.providers.registry import RegistryProvider


class ConfigurationProvider:
    """Interface for configuration providers.

    Providers resolve raw values from sources (env, files, secrets stores).
    They raise ProviderUnavailableError if the source is unavailable.
    """

    name: str = "base"

    def read(self) -> dict[str, str]:
        """Read raw values from the source.

        Returns a flat dict of string key-value pairs.
        Raises ProviderUnavailableError if the source is unavailable.
        """
        raise NotImplementedError


__all__ = [
    "ConfigurationProvider",
    "ConfigurationResolutionFailed",
    "ProviderUnavailableError",
    "RegistryProvider",
    "RegistryValidationResult",
]