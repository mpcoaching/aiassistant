from __future__ import annotations

import os

from dotenv import dotenv_values

from configuration.providers.base import SourceProvider


class EnvFileProvider(SourceProvider):
    name = "env"

    def __init__(self, env_file: str | None = None) -> None:
        self._env_file = env_file or ".env"

    def read(self) -> dict[str, str]:
        values: dict[str, str | None] = {}
        if os.path.exists(self._env_file):
            try:
                values = dict(dotenv_values(self._env_file))
            except OSError:
                values = {}

        env_overrides: dict[str, str | None] = dict(os.environ)
        values.update(env_overrides)

        return {k: v for k, v in values.items() if v is not None}

    def source_type(self) -> str:
        return "env"