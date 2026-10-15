"""Tests for RedisCache (integration-safe with mocked redis client)."""

from __future__ import annotations

from unittest.mock import MagicMock

from configuration.cache.redis_cache import RedisCache


def _make_cache() -> RedisCache:
    return RedisCache(redis_url="redis://localhost:6379", ttl_seconds=60)


def _mock_redis_client(cache: RedisCache, data: dict | None = None) -> MagicMock:
    client = MagicMock()
    if data is not None:
        import json

        client.get.return_value = json.dumps(data)
    else:
        client.get.return_value = None
    cache._client = client
    return client


def test_redis_cache_set_and_get() -> None:
    cache = _make_cache()
    data = {"contract": {"name": "ci-worker", "version": "v1"}, "status": "validated"}
    client = _mock_redis_client(cache, data=data)
    cache.set("ci-worker", "v1", data)
    client.setex.assert_called_once()
    result = cache.get("ci-worker", "v1")
    assert result is not None
    assert result["status"] == "validated"


def test_redis_cache_get_missing() -> None:
    cache = _make_cache()
    _mock_redis_client(cache, data=None)
    result = cache.get("nonexistent", "v1")
    assert result is None


def test_redis_cache_cache_key_format() -> None:
    cache = _make_cache()
    _mock_redis_client(cache, data={"key": "value"})
    cache.set("my-capability", "v2", {"key": "value"})
    result = cache.get("my-capability", "v2")
    assert result is not None
    assert result["key"] == "value"


def test_redis_cache_ttl_applied() -> None:
    cache = RedisCache(redis_url="redis://localhost:6379", ttl_seconds=300)
    client = _mock_redis_client(cache, data={"key": "value"})
    cache.set("test-capability", "v1", {"key": "value"})
    client.setex.assert_called_once()
    args = client.setex.call_args
    assert args[0][1] == 300
    result = cache.get("test-capability", "v1")
    assert result is not None
