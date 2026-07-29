from __future__ import annotations

from pydantic import BaseModel


class ConfigurationManagerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    redis_url: str = "redis://redis:6379"
    contracts_path: str = "/etc/platform/contracts"
    sources_config_path: str = "/etc/platform/sources.yaml"
    cache_ttl_seconds: int = 300