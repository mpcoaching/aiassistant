"""Tests for Configuration Manager integration - contract resolution flow."""

from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from configuration.contracts.v1.qdrant import QdrantConfiguration
from configuration.manager import ConfigurationManager
from configuration.mapping.adapter import MappingAdapter
from configuration.providers.env_file import EnvFileProvider
from configuration.providers.exceptions import ConfigurationResolutionFailed
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


def test_qdrant_yaml_contract_loads() -> None:
    contract_path = os.path.join(
        os.path.dirname(__file__), "../../../../contracts/qdrant/v1/contract.yaml"
    )
    with open(contract_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data["name"] == "qdrant"
    assert data["version"] == "v1"
    assert "QDRANT_URL" in data["requirements"]
    assert "QDRANT_API_KEY" in data["requirements"]
    assert data["validators"] == ["required-fields"]


def test_qdrant_yaml_mapping_loads() -> None:
    mapping_path = os.path.join(
        os.path.dirname(__file__), "../../../../contracts/qdrant/v1/mapping.yaml"
    )
    with open(mapping_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data["mapping"]["QDRANT_URL"]["source_key"] == "QDRANT_URL"
    assert data["mapping"]["QDRANT_API_KEY"]["source_key"] == "QDRANT_KEY"


def test_qdrant_mapping_translates_legacy_key() -> None:
    raw_values = {
        "QDRANT_URL": "https://qdrant.local.test",
        "QDRANT_KEY": "legacy-secret",
    }
    mapping_rules = {
        "QDRANT_URL": {"source_key": "QDRANT_URL"},
        "QDRANT_API_KEY": {"source_key": "QDRANT_KEY"},
    }
    adapter = MappingAdapter(mapping_rules)
    resolved = adapter.map(raw_values)
    assert resolved["QDRANT_URL"] == "https://qdrant.local.test"
    assert resolved["QDRANT_API_KEY"] == "legacy-secret"


def test_qdrant_configuration_resolves_via_manager() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("QDRANT_URL=https://qdrant.local.test\n")
            f.write("QDRANT_KEY=legacy-secret\n")

        manager = ConfigurationManager(EnvFileProvider(env_file=env_file))
        cfg = manager.resolve(QdrantConfiguration)
        assert cfg.url == "https://qdrant.local.test"
        assert cfg.api_key == "legacy-secret"


def test_qdrant_configuration_resolves_with_canonical_key() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("QDRANT_URL=https://qdrant.local.test\n")
            f.write("QDRANT_API_KEY=canonical-secret\n")

        manager = ConfigurationManager(EnvFileProvider(env_file=env_file))
        cfg = manager.resolve(QdrantConfiguration)
        assert cfg.url == "https://qdrant.local.test"
        assert cfg.api_key == "canonical-secret"


def test_qdrant_configuration_fails_without_key() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("QDRANT_URL=https://qdrant.local.test\n")

        manager = ConfigurationManager(EnvFileProvider(env_file=env_file))
        with pytest.raises(ConfigurationResolutionFailed):
            manager.resolve(QdrantConfiguration)


def test_qdrant_configuration_default_url() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("QDRANT_API_KEY=secret\n")

        manager = ConfigurationManager(EnvFileProvider(env_file=env_file))
        cfg = manager.resolve(QdrantConfiguration)
        assert cfg.url == "https://qdrant.local.test"
        assert cfg.api_key == "secret"
