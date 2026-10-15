from __future__ import annotations

import json
import os

from configuration.providers.base import SourceProvider


class LocalConfigStoreProvider(SourceProvider):
    name = "local"

    def __init__(self, path: str = "/etc/platform/config.d") -> None:
        self._path = path

    def read(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if not os.path.isdir(self._path):
            return result

        for filename in sorted(os.listdir(self._path)):
            filepath = os.path.join(self._path, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if not content:
                    continue
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            result[k] = str(v)
                    else:
                        result[filename] = content
                except (json.JSONDecodeError, ValueError):
                    result[filename] = content
            except OSError:
                continue

        return result

    def source_type(self) -> str:
        return "local"