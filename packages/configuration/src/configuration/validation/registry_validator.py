from __future__ import annotations

import base64
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from configuration.validation.result import ValidationResult


class RegistryValidator:
    def validate(
        self, contract_definition: dict[str, Any], resolved: dict[str, Any]
    ) -> ValidationResult:
        errors: list[str] = []
        requirements = contract_definition.get("requirements", {})

        self._check_endpoint_connectivity(requirements, resolved, errors)
        self._check_authentication(requirements, resolved, errors)

        return ValidationResult(
            valid=len(errors) == 0,
            contract_name=contract_definition.get("name", "unknown"),
            contract_version=contract_definition.get("version", "unknown"),
            errors=errors,
            validated_at=datetime.now(UTC).isoformat(),
        )

    def _check_endpoint_connectivity(
        self,
        requirements: dict[str, Any],
        resolved: dict[str, str],
        errors: list[str],
    ) -> None:
        endpoint = str(resolved.get("REGISTRY_ENDPOINT", ""))
        if not endpoint:
            errors.append("Missing REGISTRY_ENDPOINT")
            return

        try:
            req = urllib.request.Request(endpoint.rstrip("/") + "/v2/", method="HEAD")
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                return
            errors.append(f"Registry endpoint returned {exc.code}: {endpoint}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Registry endpoint unreachable: {endpoint} ({exc})")

    def _check_authentication(
        self,
        requirements: dict[str, Any],
        resolved: dict[str, str],
        errors: list[str],
    ) -> None:
        username = resolved.get("REGISTRY_USER", "")
        password = resolved.get("REGISTRY_PASSWORD", "")
        endpoint = resolved.get("REGISTRY_ENDPOINT", "")

        if not username or not password:
            errors.append("Missing registry credentials")
            return

        if not endpoint:
            errors.append("Missing REGISTRY_ENDPOINT for authentication check")
            return

        try:
            auth = f"{username}:{password}".encode("utf-8")
            token = base64.b64encode(auth).decode("utf-8")

            req = urllib.request.Request(endpoint.rstrip("/") + "/v2/")
            req.add_header("Authorization", f"Basic {token}")

            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    errors.append(f"Unexpected status code {resp.status} from registry")
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                errors.append("Invalid registry credentials (401 Unauthorized)")
            else:
                errors.append(f"Registry returned {exc.code} during authentication check")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Cannot reach registry for authentication: {exc}")
