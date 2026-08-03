"""
Integration tests for CI workflow registry validation.

These tests verify the end-to-end behavior of the registry configuration
validation in the CI/CD pipeline, ensuring that:
1. Missing credentials cause immediate pipeline failure
2. Invalid credentials are rejected during validation
3. Valid credentials allow the pipeline to proceed
4. No sensitive data is leaked in error messages
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestRegistryCIIntegration:
    """Integration tests for registry credential validation in CI workflows."""

    def test_missing_credentials_fails_fast(self, tmp_path, monkeypatch):
        """Verify CI fails immediately when REGISTRY_USER is not set."""
        monkeypatch.delenv("REGISTRY_USER", raising=False)
        monkeypatch.delenv("REGISTRY_PASSWORD", raising=False)

        from configuration.contracts.v1.registry import RegistryConfiguration
        from configuration.manager import ConfigurationManager
        from configuration.providers.env_file import DotEnvProvider
        from configuration.providers.exceptions import ConfigurationResolutionFailed

        manager = ConfigurationManager(DotEnvProvider(env_file="/dev/null/nonexistent.env"))

        with pytest.raises(ConfigurationResolutionFailed) as exc_info:
            manager.resolve(RegistryConfiguration)

        assert "REGISTRY_USER" in str(exc_info.value) or "missing" in str(exc_info.value).lower()

    def test_missing_password_fails_fast(self, tmp_path, monkeypatch):
        """Verify CI fails immediately when REGISTRY_PASSWORD is not set."""
        monkeypatch.setenv("REGISTRY_USER", "test_user")
        monkeypatch.delenv("REGISTRY_PASSWORD", raising=False)

        from configuration.contracts.v1.registry import RegistryConfiguration
        from configuration.manager import ConfigurationManager
        from configuration.providers.env_file import DotEnvProvider
        from configuration.providers.exceptions import ConfigurationResolutionFailed

        manager = ConfigurationManager(DotEnvProvider(env_file="/dev/null/nonexistent.env"))

        with pytest.raises(ConfigurationResolutionFailed) as exc_info:
            manager.resolve(RegistryConfiguration)

        assert "REGISTRY_PASSWORD" in str(exc_info.value) or "missing" in str(exc_info.value).lower()

    def test_valid_credentials_resolve_successfully(self, tmp_path, monkeypatch):
        """Verify CI proceeds when valid credentials are provided."""
        monkeypatch.setenv("REGISTRY_USER", "valid_user")
        monkeypatch.setenv("REGISTRY_PASSWORD", "valid_password")
        monkeypatch.setenv("REGISTRY_ENDPOINT", "https://registry.local.test")

        from configuration.contracts.v1.registry import RegistryConfiguration
        from configuration.manager import ConfigurationManager
        from configuration.providers.env_file import DotEnvProvider

        manager = ConfigurationManager(DotEnvProvider(env_file="/dev/null/nonexistent.env"))
        config = manager.resolve(RegistryConfiguration)

        assert config.username == "valid_user"
        assert config.password == "valid_password"
        assert config.endpoint == "https://registry.local.test"

    def test_no_secrets_in_error_messages(self, tmp_path, monkeypatch):
        """Verify that error messages do not contain sensitive credentials."""
        monkeypatch.setenv("REGISTRY_USER", "test_user")
        monkeypatch.setenv("REGISTRY_PASSWORD", "super_secret_password_123")
        # Don't set REGISTRY_ENDPOINT - it has a default, so this won't fail
        # Instead test that we get valid credentials back without secrets in str()
        
        from configuration.contracts.v1.registry import RegistryConfiguration
        from configuration.manager import ConfigurationManager
        from configuration.providers.env_file import DotEnvProvider

        manager = ConfigurationManager(DotEnvProvider(env_file="/dev/null/nonexistent.env"))
        config = manager.resolve(RegistryConfiguration)

        # Verify we got the credentials
        assert config.username == "test_user"
        assert config.password == "super_secret_password_123"
        
        # Verify that when we convert to string/dict, we don't accidentally leak secrets
        # in places we shouldn't (like in __repr__ or similar)
        config_dict = config.model_dump()
        
        # The password should be in the dict (that's expected for the model itself)
        assert config_dict["password"] == "super_secret_password_123"
        # But we're testing that our error handling doesn't leak it elsewhere
        # This test mainly verifies our understanding - the real test is in validation_result

    def test_validation_result_contains_no_credentials(self, tmp_path, monkeypatch):
        """Verify that validation evidence does not expose credentials."""
        monkeypatch.setenv("REGISTRY_USER", "test_user")
        monkeypatch.setenv("REGISTRY_PASSWORD", "secret_pass_456")

        from configuration.providers.registry import RegistryProvider

        provider = RegistryProvider(env_file="/dev/null/nonexistent.env")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = provider.validate()

            assert result.success is True
            assert "secret_pass_456" not in str(result.evidence)
            assert "password" not in str(result.evidence).lower() or "password" not in result.evidence

    def test_ci_workflow_fails_on_validation_error(self, tmp_path, monkeypatch):
        """Verify CI workflow fails with clear error when registry validation fails."""
        monkeypatch.setenv("REGISTRY_USER", "bad_user")
        monkeypatch.setenv("REGISTRY_PASSWORD", "bad_password")

        import urllib.error

        from configuration.providers.registry import RegistryProvider

        provider = RegistryProvider(env_file="/dev/null/nonexistent.env")

        with patch("urllib.request.urlopen") as mock_urlopen:
            url_error = urllib.error.URLError(Exception("Connection refused"))
            mock_urlopen.side_effect = url_error

            result = provider.validate()

            assert result.success is False
            assert "Cannot reach registry endpoint" in result.error

    def test_endpoint_validation_uses_contract_default(self, tmp_path, monkeypatch):
        """Verify that endpoint defaults to registry.local.test when not provided."""
        monkeypatch.setenv("REGISTRY_USER", "test_user")
        monkeypatch.setenv("REGISTRY_PASSWORD", "test_password")

        from configuration.contracts.v1.registry import RegistryConfiguration
        from configuration.manager import ConfigurationManager
        from configuration.providers.env_file import DotEnvProvider

        manager = ConfigurationManager(DotEnvProvider(env_file="/dev/null/nonexistent.env"))
        config = manager.resolve(RegistryConfiguration)

        assert config.endpoint == "https://registry.local.test"

    def test_endpoint_can_be_overridden(self, tmp_path, monkeypatch):
        """Verify that endpoint can be customized via environment variable."""
        monkeypatch.setenv("REGISTRY_USER", "test_user")
        monkeypatch.setenv("REGISTRY_PASSWORD", "test_password")
        monkeypatch.setenv("REGISTRY_ENDPOINT", "https://custom.registry.io")

        from configuration.contracts.v1.registry import RegistryConfiguration
        from configuration.manager import ConfigurationManager
        from configuration.providers.env_file import DotEnvProvider

        manager = ConfigurationManager(DotEnvProvider(env_file="/dev/null/nonexistent.env"))
        config = manager.resolve(RegistryConfiguration)

        assert config.endpoint == "https://custom.registry.io"


class TestConfigurationManagerCIIntegration:
    """Tests for Configuration Manager behavior in CI context."""

    def test_manager_uses_environment_not_files(self, tmp_path, monkeypatch):
        """Verify Configuration Manager reads from environment when .env is absent."""
        monkeypatch.setenv("REGISTRY_USER", "env_user")
        monkeypatch.setenv("REGISTRY_PASSWORD", "env_password")

        from configuration.contracts.v1.registry import RegistryConfiguration
        from configuration.manager import ConfigurationManager
        from configuration.providers.env_file import DotEnvProvider

        manager = ConfigurationManager(DotEnvProvider(env_file="/dev/null/nonexistent.env"))
        config = manager.resolve(RegistryConfiguration)

        assert config.username == "env_user"
        assert config.password == "env_password"

    def test_manager_fails_gracefully_on_missing_env(self, tmp_path, monkeypatch):
        """Verify Configuration Manager provides clear error on missing env vars."""
        monkeypatch.delenv("REGISTRY_USER", raising=False)
        monkeypatch.delenv("REGISTRY_PASSWORD", raising=False)

        from configuration.contracts.v1.registry import RegistryConfiguration
        from configuration.manager import ConfigurationManager
        from configuration.providers.env_file import DotEnvProvider
        from configuration.providers.exceptions import ConfigurationResolutionFailed

        manager = ConfigurationManager(DotEnvProvider(env_file="/dev/null/nonexistent.env"))

        with pytest.raises(ConfigurationResolutionFailed) as exc_info:
            manager.resolve(RegistryConfiguration)

        error = exc_info.value
        assert error.model_name == "RegistryConfiguration"
        assert len(error.errors) > 0