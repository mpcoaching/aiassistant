"""Tests for EnvFileProvider source provider."""

from __future__ import annotations

import os
import tempfile

from configuration.providers.env_file import EnvFileProvider


def test_env_file_provider_reads_env_file() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("KEY1=value1\nKEY2=value2\n")
        f.flush()
        tmp_path = f.name

    try:
        provider = EnvFileProvider(env_file=tmp_path)
        result = provider.read()
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"
    finally:
        os.unlink(tmp_path)


def test_env_file_provider_os_environ_overrides() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("KEY1=from_env_file\nKEY2=from_env_file\n")
        tmp_path = f.name

    try:
        os.environ["KEY1"] = "from_os_environ"
        provider = EnvFileProvider(env_file=tmp_path)
        result = provider.read()
        assert result["KEY1"] == "from_os_environ"
        assert result["KEY2"] == "from_env_file"
    finally:
        os.unlink(tmp_path)
        os.environ.pop("KEY1", None)


def test_env_file_provider_missing_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = os.path.join(tmpdir, "nonexistent.env")
        provider = EnvFileProvider(env_file=nonexistent)
        result = provider.read()
        # When the file doesn't exist, .env contributions are empty.
        # os.environ values may still be present from the system environment.
        # We only assert that no KeyError or crash occurs.
        assert isinstance(result, dict)


def test_env_file_provider_name() -> None:
    provider = EnvFileProvider()
    assert provider.name == "env"


def test_env_file_provider_source_type() -> None:
    provider = EnvFileProvider()
    assert provider.source_type() == "env"