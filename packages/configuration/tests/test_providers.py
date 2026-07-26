"""
Tests for configuration providers.
"""

from __future__ import annotations

from configuration.providers import ConfigurationProvider, ProviderUnavailableError


class TestProviderUnavailableError:
    def test_is_exception(self):
        assert issubclass(ProviderUnavailableError, Exception)


class TestDotEnvProvider:
    def test_reads_env_vars(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        monkeypatch.setenv("FOO", "env_override")
        monkeypatch.delenv("BAZ", raising=False)

        from configuration.providers.dotenv import DotEnvProvider

        provider = DotEnvProvider(env_file=str(env_file))
        result = provider.read()
        assert result["FOO"] == "env_override"
        assert result["BAZ"] == "qux"

    def test_missing_env_file_falls_back_to_os_environ(self, tmp_path, monkeypatch):
        from configuration.providers.dotenv import DotEnvProvider

        monkeypatch.setenv("ONLY_IN_ENV", "from_environ")
        provider = DotEnvProvider(env_file=str(tmp_path / "nonexistent.env"))
        result = provider.read()
        assert result["ONLY_IN_ENV"] == "from_environ"

    def test_returns_flat_dict_of_strings(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value\n")
        monkeypatch.setenv("KEY", "value")

        from configuration.providers.dotenv import DotEnvProvider

        provider = DotEnvProvider(env_file=str(env_file))
        result = provider.read()
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result)
        assert all(isinstance(v, str) for v in result.values())


class FakeProvider(ConfigurationProvider):
    name = "fake"

    def __init__(self, data: dict[str, str]):
        self._data = data

    def read(self) -> dict[str, str]:
        return dict(self._data)
