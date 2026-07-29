from __future__ import annotations

from typing import Any


class MappingAdapter:
    def __init__(self, mapping_rules: dict[str, Any]) -> None:
        self._rules = mapping_rules

    def map(self, raw_values: dict[str, str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for contract_field, rule in self._rules.items():
            source_key = rule.get("source_key")
            if not source_key:
                continue
            if source_key in raw_values:
                self._set_nested(result, contract_field, raw_values[source_key])
        return result

    def _set_nested(self, obj: dict[str, Any], dotted_path: str, value: str) -> None:
        parts = dotted_path.split(".")
        current: dict[str, Any] = obj
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            if not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value