"""
Registry Provider with Validation.

Reads registry credentials from .env and validates them via the Docker
Registry HTTP API before providing them to consumers.
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from base64 import b64encode
from typing import Any

from configuration.providers.exceptions import (
    RegistryValidationResult,
)

logger = logging.getLogger(__name__)


class RegistryProvider:
    """Provider that reads registry credentials from .env and validates them."""

    name = "registry"

    def __init__(self, env_file: str | None = None) -> None:
        self._env_file = env_file or ".env"
        self._validation_result: RegistryValidationResult | None = None

    def read(self) -> dict[str, str]:
        from configuration.providers.env_file import DotEnvProvider

        raw = DotEnvProvider(env_file=self._env_file).read()
        return {k: v for k, v in raw.items() if k.startswith("REGISTRY_")}

    def validate(self) -> RegistryValidationResult:
        raw = self.read()
        username = raw.get("REGISTRY_USER", "")
        password = raw.get("REGISTRY_PASSWORD", "")
        endpoint = raw.get("REGISTRY_ENDPOINT", "https://registry.local.test")

        start = time.monotonic()
        evidence: dict[str, Any] = {
            "endpoint": endpoint,
            "username": username,
        }

        try:
            auth = f"{username}:{password}".encode()
            token = b64encode(auth).decode("utf-8")

            url = f"{endpoint.rstrip('/')}/v2/"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Basic {token}")

            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    elapsed = time.monotonic() - start
                    evidence.update(
                        {
                            "status_code": resp.status,
                            "latency_seconds": round(elapsed, 3),
                        }
                    )
                    if resp.status == 200:
                        self._validation_result = RegistryValidationResult(
                            success=True,
                            validator_id="registry-http-auth",
                            validator_version="1.0.0",
                            evidence=evidence,
                            error=None,
                        )
                    else:
                        self._validation_result = RegistryValidationResult(
                            success=False,
                            validator_id="registry-http-auth",
                            validator_version="1.0.0",
                            evidence=evidence,
                            error=f"Unexpected status code {resp.status}",
                        )
            except urllib.error.HTTPError as exc:
                elapsed = time.monotonic() - start
                if exc.code == 401:
                    self._validation_result = RegistryValidationResult(
                        success=False,
                        validator_id="registry-http-auth",
                        validator_version="1.0.0",
                        evidence={
                            **evidence,
                            "status_code": exc.code,
                            "latency_seconds": round(elapsed, 3),
                        },
                        error="Invalid registry credentials (401 Unauthorized)",
                    )
                else:
                    self._validation_result = RegistryValidationResult(
                        success=False,
                        validator_id="registry-http-auth",
                        validator_version="1.0.0",
                        evidence={
                            **evidence,
                            "status_code": exc.code,
                            "latency_seconds": round(elapsed, 3),
                        },
                        error=f"Registry returned {exc.code}",
                    )
        except (urllib.error.URLError, ValueError) as exc:
            elapsed = time.monotonic() - start
            if isinstance(exc, urllib.error.URLError):
                self._validation_result = RegistryValidationResult(
                    success=False,
                    validator_id="registry-http-auth",
                    validator_version="1.0.0",
                    evidence={
                        **evidence,
                        "error": str(exc.reason),
                        "latency_seconds": round(elapsed, 3),
                    },
                    error=f"Cannot reach registry endpoint: {exc.reason}",
                )
            else:
                self._validation_result = RegistryValidationResult(
                    success=False,
                    validator_id="registry-http-auth",
                    validator_version="1.0.0",
                    evidence={
                        **evidence,
                        "error": str(exc),
                        "latency_seconds": round(elapsed, 3),
                    },
                    error=f"Validation error: {exc}",
                )

        return self._validation_result

    def is_validated(self) -> bool:
        if self._validation_result is None:
            return False
        return self._validation_result.success

    def validation_result(self) -> RegistryValidationResult | None:
        return self._validation_result