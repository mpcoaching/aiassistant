"""Tests for JsonConfigProvider source provider."""

from __future__ import annotations

import json
import os
import tempfile

from configuration.providers.json_file import JsonConfigProvider


def test_json_config_provider_reads_config_file() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"KEY1": "value1", "KEY2": "value2"}, f)
        f.flush()
        tmp_path = f.name

    try:
        provider = JsonConfigProvider(path=tmp_path)
        result = provider.read()
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"
    finally:
        os.unlink(tmp_path)


def test_json_config_provider_missing_file() -> None:
    provider = JsonConfigProvider(path="/tmp/nonexistent_file_xyz.json")
    result = provider.read()
    assert result == {}


def test_json_config_provider_invalid_json() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not valid json")
        tmp_path = f.name

    try:
        provider = JsonConfigProvider(path=tmp_path)
        result = provider.read()
        assert result == {}
    finally:
        os.unlink(tmp_path)


def test_json_config_provider_name() -> None:
    provider = JsonConfigProvider()
    assert provider.name == "json"


def test_json_config_provider_source_type() -> None:
    provider = JsonConfigProvider()
    assert provider.source_type() == "json"
