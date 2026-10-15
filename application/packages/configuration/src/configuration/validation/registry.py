from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from configuration.validation.result import ValidationResult


class ValidatorRegistry:
    def __init__(self) -> None:
        self._validators: dict[str, Any] = {}

    def register(self, name: str, validator: Any) -> None:
        self._validators[name] = validator

    def get(self, name: str) -> Any | None:
        return self._validators.get(name)

    def list_registered(self) -> list[str]:
        return list(self._validators.keys())

    def validate_contract(
        self,
        contract_name: str,
        contract_version: str,
        contract_definition: dict[str, Any],
        resolved: dict[str, Any],
    ) -> ValidationResult:
        errors: list[str] = []
        validators = contract_definition.get("validators", [])

        for validator_name in validators:
            v = self._validators.get(validator_name)
            if v is None:
                errors.append(f"Unknown validator: {validator_name}")
                continue
            result = v.validate(contract_definition, resolved)
            if not result.valid:
                errors.extend(result.errors)

        return ValidationResult(
            valid=len(errors) == 0,
            contract_name=contract_name,
            contract_version=contract_version,
            errors=errors,
            validated_at=datetime.now(UTC).isoformat(),
        )