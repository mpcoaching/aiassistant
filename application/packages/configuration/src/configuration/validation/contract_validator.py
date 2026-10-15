from __future__ import annotations

from typing import Any

from configuration.validation.result import ValidationResult

CONSTRAINT_KEYS = {"required", "type", "pattern", "min_length", "max_length"}


class StructuralValidator:
    def validate(
        self, contract_definition: dict[str, Any], resolved: dict[str, Any]
    ) -> ValidationResult:
        errors: list[str] = []
        requirements = contract_definition.get("requirements", {})

        self._check_required_fields("", requirements, resolved, errors)

        return ValidationResult(
            valid=len(errors) == 0,
            contract_name=contract_definition.get("name", "unknown"),
            contract_version=contract_definition.get("version", "unknown"),
            errors=errors,
            validated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        )

    def _is_constraint_only(self, spec: dict[str, Any]) -> bool:
        return all(k in CONSTRAINT_KEYS for k in spec if k != "required")

    def _check_required_fields(
        self,
        prefix: str,
        schema: dict[str, Any],
        resolved: dict[str, Any],
        errors: list[str],
    ) -> None:
        for key, spec in schema.items():
            path = f"{prefix}.{key}" if prefix else key

            if isinstance(spec, dict):
                if self._is_constraint_only(spec) and "required" in spec:
                    if spec.get("required", False) and key not in resolved:
                        errors.append(f"Missing: {path}")
                elif key in resolved and isinstance(resolved[key], dict):
                    self._check_required_fields(path, spec, resolved[key], errors)
            elif isinstance(spec, bool) and spec:  # noqa: SIM102
                if key not in resolved:
                    errors.append(f"Missing: {path}")