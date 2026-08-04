"""Tests for Configuration Manager integration - contract resolution flow."""

from __future__ import annotations

import os
import tempfile

from configuration.mapping.adapter import MappingAdapter
from configuration.providers.env_file import EnvFileProvider
from configuration.validation.contract_validator import StructuralValidator
from configuration.validation.registry import ValidatorRegistry


def test_full_contract_resolution_flow() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("GITEA_URL=https://gitea.local.test\n")
            f.write("RUNNER_TOKEN=abc123\n")

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
        mapping = {
            "mapping": {
                "source_control.endpoint": {"source_key": "GITEA_URL"},
                "source_control.authentication.token": {"source_key": "RUNNER_TOKEN"},
            },
        }

        provider = EnvFileProvider(env_file=env_file)
        raw = provider.read()

        mapping_rules = mapping["mapping"]
        adapter = MappingAdapter(mapping_rules)
        resolved = adapter.map(raw)

        assert resolved["source_control"]["endpoint"] == "https://gitea.local.test"
        assert resolved["source_control"]["authentication"]["token"] == "abc123"

        registry = ValidatorRegistry()
        registry.register("required-fields", StructuralValidator())
        result = registry.validate_contract(
            contract["name"], contract["version"], contract, resolved
        )
        assert result.valid is True
        assert result.errors == []


def test_contract_resolution_fails_on_missing_required() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("GITEA_URL=https://gitea.local.test\n")

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
        mapping = {
            "mapping": {
                "source_control.endpoint": {"source_key": "GITEA_URL"},
                "source_control.authentication.token": {"source_key": "RUNNER_TOKEN"},
            },
        }

        provider = EnvFileProvider(env_file=env_file)
        raw = provider.read()

        mapping_rules = mapping["mapping"]
        adapter = MappingAdapter(mapping_rules)
        resolved = adapter.map(raw)

        assert resolved["source_control"]["endpoint"] == "https://gitea.local.test"

        registry = ValidatorRegistry()
        registry.register("required-fields", StructuralValidator())
        result = registry.validate_contract(
            contract["name"], contract["version"], contract, resolved
        )
        assert result.valid is False
        assert len(result.errors) > 0
        assert any("authentication" in err for err in result.errors)
