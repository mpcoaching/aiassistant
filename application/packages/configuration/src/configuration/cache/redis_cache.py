from __future__ import annotations

import json
from typing import Any


class RedisCache:
    def __init__(self, redis_url: str, ttl_seconds: int = 300) -> None:
        self._redis_url = redis_url
        self._ttl_seconds = ttl_seconds
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import redis as _redis
            self._client = _redis.from_url(self._redis_url)
        return self._client

    def get(self, contract_name: str, contract_version: str) -> dict[str, Any] | None:
        key = f"contract:{contract_name}:{contract_version}"
        try:
            client = self._get_client()
            data = client.get(key)
            if data is None:
                return None
            return json.loads(data)
        except Exception:  # noqa: BLE001
            return None

    def set(self, contract_name: str, contract_version: str, data: dict[str, Any]) -> None:
        key = f"contract:{contract_name}:{contract_version}"
        try:
            client = self._get_client()
            client.setex(key, self._ttl_seconds, json.dumps(data))
        except Exception:  # noqa: BLE001, S110
            pass