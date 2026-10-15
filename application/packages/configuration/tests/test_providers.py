"""
Tests for configuration providers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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

        from configuration.providers.env_file import DotEnvProvider

        provider = DotEnvProvider(env_file=str(env_file))
        result = provider.read()
        assert result["FOO"] == "env_override"
        assert result["BAZ"] == "qux"

    def test_missing_env_file_falls_back_to_os_environ(self, tmp_path, monkeypatch):
        from configuration.providers.env_file import DotEnvProvider

        monkeypatch.setenv("ONLY_IN_ENV", "from_environ")
        provider = DotEnvProvider(env_file=str(tmp_path / "nonexistent.env"))
        result = provider.read()
        assert result["ONLY_IN_ENV"] == "from_environ"

    def test_returns_flat_dict_of_strings(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value\n")
        monkeypatch.setenv("KEY", "value")

        from configuration.providers.env_file import DotEnvProvider

        provider = DotEnvProvider(env_file=str(env_file))
        result = provider.read()
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result)
        assert all(isinstance(v, str) for v in result.values())


class TestRegistryProvider:
    def test_reads_registry_vars(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("REGISTRY_USER=testuser\nREGISTRY_PASSWORD=testpass\nREGISTRY_ENDPOINT=https://my.registry.io\nOTHER=ignore\n")
        monkeypatch.delenv("REGISTRY_USER", raising=False)
        monkeypatch.delenv("REGISTRY_PASSWORD", raising=False)
        monkeypatch.delenv("REGISTRY_ENDPOINT", raising=False)
        monkeypatch.setenv("REGISTRY_USER", "env_override")

        from configuration.providers.registry import RegistryProvider

        provider = RegistryProvider(env_file=str(env_file))
        result = provider.read()

        assert result["REGISTRY_USER"] == "env_override"
        assert result["REGISTRY_PASSWORD"] == "testpass"
        assert result["REGISTRY_ENDPOINT"] == "https://my.registry.io"
        assert "OTHER" not in result

    def test_missing_env_file_falls_back_to_os_environ(self, tmp_path, monkeypatch):
        from configuration.providers.registry import RegistryProvider

        monkeypatch.setenv("REGISTRY_USER", "from_env")
        monkeypatch.setenv("REGISTRY_PASSWORD", "from_env")
        provider = RegistryProvider(env_file=str(tmp_path / "nonexistent.env"))
        result = provider.read()
        assert result["REGISTRY_USER"] == "from_env"
        assert result["REGISTRY_PASSWORD"] == "from_env"

    @patch("urllib.request.urlopen")
    def test_validate_success(self, mock_urlopen, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("REGISTRY_USER=user\nREGISTRY_PASSWORD=pass\nREGISTRY_ENDPOINT=https://registry.example.com\n")
        monkeypatch.delenv("REGISTRY_USER", raising=False)
        monkeypatch.delenv("REGISTRY_PASSWORD", raising=False)
        monkeypatch.delenv("REGISTRY_ENDPOINT", raising=False)

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from configuration.providers.registry import RegistryProvider

        provider = RegistryProvider(env_file=str(env_file))
        result = provider.validate()

        assert result.success is True
        assert result.validator_id == "registry-http-auth"
        assert result.validator_version == "1.0.0"
        assert result.error is None
        assert result.evidence["endpoint"] == "https://registry.example.com"
        assert result.evidence["username"] == "user"
        assert result.evidence["status_code"] == 200
        assert "latency_seconds" in result.evidence
        assert provider.is_validated() is True
        assert provider.validation_result() is result

    @patch("urllib.request.urlopen")
    def test_validate_invalid_credentials_401(self, mock_urlopen, tmp_path, monkeypatch):
        import urllib.error

        env_file = tmp_path / ".env"
        env_file.write_text("REGISTRY_USER=baduser\nREGISTRY_PASSWORD=badpass\n")

        mock_resp = MagicMock()
        mock_resp.status = 401
        http_error = urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)
        mock_urlopen.side_effect = http_error

        from configuration.providers.registry import RegistryProvider

        provider = RegistryProvider(env_file=str(env_file))
        result = provider.validate()

        assert result.success is False
        assert result.validator_id == "registry-http-auth"
        assert result.error == "Invalid registry credentials (401 Unauthorized)"
        assert result.evidence["status_code"] == 401
        assert provider.is_validated() is False

    @patch("urllib.request.urlopen")
    def test_validate_other_http_error(self, mock_urlopen, tmp_path, monkeypatch):
        import urllib.error

        env_file = tmp_path / ".env"
        env_file.write_text("REGISTRY_USER=user\nREGISTRY_PASSWORD=pass\n")

        http_error = urllib.error.HTTPError("url", 500, "Internal Server Error", {}, None)
        mock_urlopen.side_effect = http_error

        from configuration.providers.registry import RegistryProvider

        provider = RegistryProvider(env_file=str(env_file))
        result = provider.validate()

        assert result.success is False
        assert result.error == "Registry returned 500"
        assert result.evidence["status_code"] == 500

    @patch("urllib.request.urlopen")
    def test_validate_unreachable_endpoint(self, mock_urlopen, tmp_path, monkeypatch):
        import urllib.error

        env_file = tmp_path / ".env"
        env_file.write_text("REGISTRY_USER=user\nREGISTRY_PASSWORD=pass\nREGISTRY_ENDPOINT=https://unreachable.registry\n")

        url_error = urllib.error.URLError(ConnectionError("Connection refused"))
        mock_urlopen.side_effect = url_error

        from configuration.providers.registry import RegistryProvider

        provider = RegistryProvider(env_file=str(env_file))
        result = provider.validate()

        assert result.success is False
        assert "Cannot reach registry endpoint" in result.error
        assert result.evidence["error"] == "Connection refused"

    @patch("urllib.request.urlopen")
    def test_validate_unexpected_error(self, mock_urlopen, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("REGISTRY_USER=user\nREGISTRY_PASSWORD=pass\n")

        mock_urlopen.side_effect = ValueError("unexpected error")

        from configuration.providers.registry import RegistryProvider

        provider = RegistryProvider(env_file=str(env_file))
        result = provider.validate()

        assert result.success is False
        assert "Validation error: unexpected error" in result.error

    def test_is_validated_before_validate(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("REGISTRY_USER=user\nREGISTRY_PASSWORD=pass\n")

        from configuration.providers.registry import RegistryProvider

        provider = RegistryProvider(env_file=str(env_file))
        assert provider.is_validated() is False
        assert provider.validation_result() is None

    def test_validation_result_structure(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("REGISTRY_USER=user\nREGISTRY_PASSWORD=pass\n")

        from configuration.providers.registry import RegistryProvider, RegistryValidationResult

        provider = RegistryProvider(env_file=str(env_file))

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = provider.validate()

        assert isinstance(result, RegistryValidationResult)
        assert hasattr(result, "timestamp")
        assert result.timestamp is not None
        assert isinstance(result.evidence, dict)


class FakeProvider(ConfigurationProvider):
    name = "fake"

    def __init__(self, data: dict[str, str]):
        self._data = data

    def read(self) -> dict[str, str]:
        return dict(self._data)
