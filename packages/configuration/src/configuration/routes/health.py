from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from configuration.cache.redis_cache import RedisCache
from configuration.config import ConfigurationManagerConfig
from configuration.sources import init_providers, load_sources_config

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict:
    return {"status": "healthy"}


@router.get("/ready")
def ready() -> dict:
    errors: list[str] = []

    config = ConfigurationManagerConfig()
    cache = RedisCache(redis_url=config.redis_url)
    try:
        client = cache._get_client()
        client.ping()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis unavailable: %s", exc)
        errors.append(f"Redis unavailable: {exc}")

    sources_config = load_sources_config()
    provider_info = init_providers(sources_config)
    if not provider_info.get("providers"):
        errors.append("No source providers initialized")

    contracts_path = config.contracts_path
    import os

    if not os.path.exists(contracts_path):
        errors.append(f"Contracts path does not exist: {contracts_path}")

    if errors:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "errors": errors})

    return {"status": "ready"}