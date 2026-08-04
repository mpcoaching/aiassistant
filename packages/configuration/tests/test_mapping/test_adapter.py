"""Tests for MappingAdapter."""

from __future__ import annotations

from configuration.mapping.adapter import MappingAdapter


def test_mapping_adapter_maps_simple_values() -> None:
    rules = {
        "source_control.endpoint": {"source_key": "GITEA_URL"},
        "source_control.authentication.token": {"source_key": "RUNNER_TOKEN"},
    }
    adapter = MappingAdapter(rules)
    raw = {"GITEA_URL": "https://gitea.local.test", "RUNNER_TOKEN": "abc123"}
    result = adapter.map(raw)
    assert result["source_control"]["endpoint"] == "https://gitea.local.test"
    assert result["source_control"]["authentication"]["token"] == "abc123"


def test_mapping_adapter_missing_key_omits_field() -> None:
    rules = {
        "source_control.endpoint": {"source_key": "GITEA_URL"},
        "source_control.authentication.token": {"source_key": "RUNNER_TOKEN"},
    }
    adapter = MappingAdapter(rules)
    raw = {"GITEA_URL": "https://gitea.local.test"}
    result = adapter.map(raw)
    assert result["source_control"]["endpoint"] == "https://gitea.local.test"
    assert "token" not in result["source_control"].get("authentication", {})


def test_mapping_adapter_empty_rules() -> None:
    adapter = MappingAdapter({})
    raw = {"KEY1": "value1"}
    result = adapter.map(raw)
    assert result == {}


def test_mapping_adapter_precedence() -> None:
    rules = {
        "endpoint": {"source_key": "PRIMARY_URL"},
    }
    adapter = MappingAdapter(rules)
    raw = {"PRIMARY_URL": "https://primary.example.com"}
    result = adapter.map(raw)
    assert result["endpoint"] == "https://primary.example.com"
