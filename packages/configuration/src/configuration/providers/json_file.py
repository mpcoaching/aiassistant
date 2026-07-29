from __future__ import annotations

import json
import os

from configuration.providers.base import SourceProvider


class JsonConfigProvider(SourceProvider):
    name = "json"

    def __init__(self, path: str = "/etc/platform/config.json") -> None:
        self._path = path

    def read(self) -> dict[str, str]:
        if not os.path.exists(self._path):
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {k: str(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError):
            return {}

    def source_type(self) -> str:
        return "json"