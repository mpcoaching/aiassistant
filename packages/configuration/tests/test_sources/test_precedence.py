"""Tests for configuration source loading and precedence."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from configuration.providers.env_file import EnvFileProvider
from configuration.providers.json_file import JsonConfigProvider
from configuration.sources.loader import load_sources_config
from configuration.sources.precedence import resolve_precedence


def test_load_sources_config_default() -> None:
    config = load_sources_config("/nonexistent/path/sources.yaml")
    assert "sources" in config
    assert len(config["sources"]["providers"]) == 3


def test_load_sources_config_valid_file() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("sources:\n  providers:\n    - type: env\n      enabled: true\n  precedence:\n    - env\n")
        tmp_path = f.name

    try:
        config = load_sources_config(tmp_path)
        assert config["sources"]["providers"][0]["type"] == "env"
    finally:
        os.unlink(tmp_path)


def test_resolve_precedence_empty() -> None:
    result = resolve_precedence({}, [])
    assert result == []


def test_resolve_precedence_with_providers() -> None:
    provider = EnvFileProvider()
    providers = {"env": provider}
    precedence = ["env"]
    result = resolve_precedence(providers, precedence)
    assert len(result) == 1
    assert result[0] is provider


def test_env_file_provider_reads_env_file(tmp_path: Any) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KEY1=value1\nKEY2=value2\n")

    provider = EnvFileProvider(env_file=str(env_file))
    result = provider.read()
    assert result["KEY1"] == "value1"
    assert result["KEY2"] == "value2"


def test_precedence_env_wins_over_json() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("GITEA_URL=https://env.local.test\n")

        json_file = os.path.join(tmpdir, "config.json")
        with open(json_file, "w") as f:
            json.dump({"GITEA_URL": "https://json.local.test"}, f)

        env_provider = EnvFileProvider(env_file=env_file)
        json_provider = JsonConfigProvider(path=json_file)

        env_result = env_provider.read()
        json_result = json_provider.read()

        assert env_result["GITEA_URL"] == "https://env.local.test"
        assert json_result["GITEA_URL"] == "https://json.local.test"