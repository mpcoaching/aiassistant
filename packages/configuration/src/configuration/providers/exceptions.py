"""
Provider Exceptions

Shared exceptions and result types for providers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class ProviderUnavailableError(Exception):
    """Raised when a configuration source is unavailable."""


class ConfigurationResolutionFailed(Exception):
    """Raised when configuration validation fails or required fields are missing."""

    def __init__(self, model_name: str, errors: list[str]):
        self.model_name = model_name
        self.errors = errors
        super().__init__(
            f"ConfigurationResolutionFailed: could not resolve {model_name}. "
            + "; ".join(errors)
        )


class RegistryValidationResult:
    """Result of validating registry credentials."""

    def __init__(
        self,
        success: bool,
        validator_id: str,
        validator_version: str,
        evidence: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        self.success = success
        self.validator_id = validator_id
        self.validator_version = validator_version
        self.evidence = evidence or {}
        self.error = error
        self.timestamp = datetime.now()