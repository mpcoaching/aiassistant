from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    contract_name: str
    contract_version: str
    errors: list[str]
    validated_at: str