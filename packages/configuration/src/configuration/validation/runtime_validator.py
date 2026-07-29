from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from configuration.validation.result import ValidationResult


class RuntimeValidator:
    def validate(
        self, contract_definition: dict[str, Any], resolved: dict[str, Any]
    ) -> ValidationResult:
        errors: list[str] = []
        requirements = contract_definition.get("requirements", {})

        self._check_connectivity(requirements, resolved, errors)
        self._check_authentication(requirements, resolved, errors)

        return ValidationResult(
            valid=len(errors) == 0,
            contract_name=contract_definition.get("name", "unknown"),
            contract_version=contract_definition.get("version", "unknown"),
            errors=errors,
            validated_at=datetime.now(UTC).isoformat(),
        )

    def _check_connectivity(
        self,
        requirements: dict[str, Any],
        resolved: dict[str, str],
        errors: list[str],
    ) -> None:
        source_ctrl = requirements.get("source_control", {})
        endpoint_req = source_ctrl.get("endpoint", {})
        source_control: dict[str, Any] = resolved.get("source_control", {})  # type: ignore[assignment]
        if not isinstance(source_control, dict):
            return
        if isinstance(endpoint_req, dict) and endpoint_req.get("required", False) and "endpoint" in source_control:
            endpoint = str(source_control["endpoint"])
            import urllib.request
            try:
                req = urllib.request.Request(endpoint, method="HEAD")
                urllib.request.urlopen(req, timeout=5)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Endpoint unreachable: {endpoint} ({exc})")

    def _check_authentication(
        self,
        requirements: dict[str, Any],
        resolved: dict[str, str],
        errors: list[str],
    ) -> None:
        source_ctrl = requirements.get("source_control", {})
        auth_req = source_ctrl.get("authentication", {})
        source_control: dict[str, Any] = resolved.get("source_control", {})  # type: ignore[assignment]
        if not isinstance(source_control, dict):
            return
        if isinstance(auth_req, dict) and auth_req.get("required", False) and "authentication" in source_control:
            auth_data = source_control.get("authentication", {})
            if isinstance(auth_data, dict):
                token = auth_data.get("token", "")
                if not token:
                    errors.append("Missing authentication token")