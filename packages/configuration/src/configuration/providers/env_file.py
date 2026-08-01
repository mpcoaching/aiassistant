"""
DotEnv Provider

Reads configuration from .env files and os.environ.
"""

from __future__ import annotations

import os

from dotenv import dotenv_values

from configuration.providers import ConfigurationProvider
from configuration.providers.exceptions import ProviderUnavailableError


class DotEnvProvider(ConfigurationProvider):
    """Provider that reads configuration from .env files and os.environ."""

    name = "dotenv"

    def __init__(self, env_file: str | None = None) -> None:
        self._env_file = env_file or ".env"

    def read(self) -> dict[str, str]:
        values: dict[str, str | None] = {}
        if os.path.exists(self._env_file):
            try:
                values = dict(dotenv_values(self._env_file))
            except OSError as exc:
                raise ProviderUnavailableError(f"Cannot read .env file {self._env_file}: {exc}") from exc

        env_overrides: dict[str, str | None] = dict(os.environ)
        values.update(env_overrides)

        return {k: v for k, v in values.items() if v is not None}
