"""
Configuration Providers

Providers are adapters that translate external configuration sources into
internal configuration contracts. Consumers never interact with providers
directly — the Configuration Manager selects and orchestrates them.
"""

from __future__ import annotations

from typing import Any, Dict


class ProviderUnavailableError(Exception):
    """Raised when a configuration source is unavailable."""


class ConfigurationResolutionFailed(Exception):
    """Raised when configuration validation fails or required fields are missing."""

    def __init__(self, model_name: str, errors: list[str]) -> None:
        self.model_name = model_name
        self.errors = errors
        super().__init__(
            f"ConfigurationResolutionFailed: could not resolve {model_name}. "
            + "; ".join(errors)
        )


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
]
