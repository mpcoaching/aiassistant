from __future__ import annotations

from typing import Any


def load_sources_config(path: str = "/etc/platform/sources.yaml") -> dict[str, Any]:
    import yaml

    if not path or not __import__("os").path.exists(path):
        return _default_sources_config()

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return _default_sources_config()

    return data


def _default_sources_config() -> dict[str, Any]:
    return {
        "sources": {
            "providers": [
                {"type": "env", "enabled": True},
                {"type": "json", "enabled": True, "path": "/etc/platform/config.json"},
                {"type": "local", "enabled": True, "path": "/etc/platform/config.d"},
            ],
            "precedence": ["env", "json", "local"],
        }
    }