"""Tests for ValidatorRegistry."""

from __future__ import annotations

import pytest

from configuration.validation.contract_validator import StructuralValidator
from configuration.validation.registry import ValidatorRegistry


def test_validator_registry_register_and_get() -> None:
    registry = ValidatorRegistry()
    validator = StructuralValidator()
    registry.register("required-fields", validator)
    assert registry.get("required-fields") is validator


def test_validator_registry_get_unknown() -> None:
    registry = ValidatorRegistry()
    assert registry.get("unknown") is None


def test_validator_registry_list_registered() -> None:
    registry = ValidatorRegistry()
    registry.register("v1", StructuralValidator())
    registry.register("v2", StructuralValidator())
    names = registry.list_registered()
    assert "v1" in names
    assert "v2" in names


def test_validator_registry_validate_contract_with_all_validators_pass() -> None:
    registry = ValidatorRegistry()
    structural = StructuralValidator()
    registry.register("required-fields", structural)

    contract = {
        "name": "ci-worker",
        "version": "v1",
        "requirements": {
            "source_control": {
                "endpoint": {"required": True},
            },
        },
        "validators": ["required-fields"],
    }
    resolved = {
        "source_control": {
            "endpoint": "https://gitea.local.test",
        },
    }
    result = registry.validate_contract("ci-worker", "v1", contract, resolved)
    assert result.valid is True


def test_validator_registry_validate_contract_with_unknown_validator() -> None:
    registry = ValidatorRegistry()
    contract = {
        "name": "ci-worker",
        "version": "v1",
        "requirements": {},
        "validators": ["unknown-validator"],
    }
    resolved = {}
    result = registry.validate_contract("ci-worker", "v1", contract, resolved)
    assert result.valid is False
    assert any("Unknown validator" in err for err in result.errors)


def test_validator_registry_validate_contract_with_multiple_validators() -> None:
    registry = ValidatorRegistry()
    structural = StructuralValidator()
    registry.register("required-fields", structural)

    contract = {
        "name": "ci-worker",
        "version": "v1",
        "requirements": {
            "source_control": {
                "endpoint": {"required": True},
                "authentication": {"required": True},
            },
        },
        "validators": ["required-fields"],
    }
    resolved = {
        "source_control": {
            "endpoint": "https://gitea.local.test",
        },
    }
    result = registry.validate_contract("ci-worker", "v1", contract, resolved)
    assert result.valid is False
    assert len(result.errors) > 0