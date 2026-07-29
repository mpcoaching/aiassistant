"""Tests for LocalConfigStoreProvider source provider."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from configuration.providers.local_store import LocalConfigStoreProvider


def test_local_config_store_provider_reads_json_files() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "app.json"), "w") as f:
            json.dump({"KEY1": "value1", "KEY2": "value2"}, f)

        provider = LocalConfigStoreProvider(path=tmpdir)
        result = provider.read()
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"


def test_local_config_store_provider_reads_plain_files() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "key1.txt"), "w") as f:
            f.write("plain_value")

        provider = LocalConfigStoreProvider(path=tmpdir)
        result = provider.read()
        assert result["key1.txt"] == "plain_value"


def test_local_config_store_provider_missing_directory() -> None:
    provider = LocalConfigStoreProvider(path="/tmp/nonexistent_dir_xyz")
    result = provider.read()
    assert result == {}


def test_local_config_store_provider_name() -> None:
    provider = LocalConfigStoreProvider()
    assert provider.name == "local"


def test_local_config_store_provider_source_type() -> None:
    provider = LocalConfigStoreProvider()
    assert provider.source_type() == "local"