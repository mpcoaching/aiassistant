from __future__ import annotations

from typing import Any

from configuration.providers.base import SourceProvider
from configuration.sources.loader import load_sources_config


def init_providers(config: dict[str, Any] | None = None) -> dict[str, Any]:
    if config is None:
        config = load_sources_config()

    sources = config.get("sources", config)
    providers_cfg = sources.get("providers", [])
    precedence = sources.get("precedence", [])

    provider_map: dict[str, SourceProvider] = {}

    for p in providers_cfg:
        if not p.get("enabled", False):
            continue
        ptype = p.get("type")
        if ptype == "env":
            from configuration.providers.env_file import EnvFileProvider
            provider_map["env"] = EnvFileProvider()
        elif ptype == "json":
            from configuration.providers.json_file import JsonConfigProvider
            provider_map["json"] = JsonConfigProvider(path=p.get("path", "/etc/platform/config.json"))
        elif ptype == "local":
            from configuration.providers.local_store import LocalConfigStoreProvider
            provider_map["local"] = LocalConfigStoreProvider(path=p.get("path", "/etc/platform/config.d"))

    return {"providers": provider_map, "precedence": precedence}