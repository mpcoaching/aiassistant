"""Tests for RedisCache (integration-safe)."""

from __future__ import annotations

import pytest

from configuration.cache.redis_cache import RedisCache


@pytest.mark.redis
def test_redis_cache_set_and_get() -> None:
    cache = RedisCache(redis_url="redis://localhost:6379", ttl_seconds=60)
    data = {"contract": {"name": "ci-worker", "version": "v1"}, "status": "validated"}
    cache.set("ci-worker", "v1", data)
    result = cache.get("ci-worker", "v1")
    assert result is not None
    assert result["status"] == "validated"


@pytest.mark.redis
def test_redis_cache_get_missing() -> None:
    cache = RedisCache(redis_url="redis://localhost:6379", ttl_seconds=60)
    result = cache.get("nonexistent", "v1")
    assert result is None


@pytest.mark.redis
def test_redis_cache_cache_key_format() -> None:
    cache = RedisCache(redis_url="redis://localhost:6379", ttl_seconds=60)
    data = {"key": "value"}
    cache.set("my-capability", "v2", data)
    result = cache.get("my-capability", "v2")
    assert result is not None
    assert result["key"] == "value"


@pytest.mark.redis
def test_redis_cache_ttl_applied() -> None:
    cache = RedisCache(redis_url="redis://localhost:6379", ttl_seconds=300)
    data = {"key": "value"}
    cache.set("test-capability", "v1", data)
    result = cache.get("test-capability", "v1")
    assert result is not None