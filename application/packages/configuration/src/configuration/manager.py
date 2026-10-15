"""
Configuration Manager

Resolves configuration models from providers and caches the results.
"""

from __future__ import annotations

import typing

from pydantic import BaseModel, ValidationError

from configuration.providers import ConfigurationProvider, ConfigurationResolutionFailed


class ConfigurationManager:
    """Resolves configuration models from providers.

    The manager reads raw values from a provider, validates them against
    Pydantic models, and caches the results for the application lifetime.
    """

    def __init__(self, provider: ConfigurationProvider) -> None:
        self._provider = provider
        self._cache: dict[type[BaseModel], BaseModel] = {}

    def resolve(self, model_cls: type[typing.Any]) -> typing.Any:
        """Resolve a configuration model via the provider.

        Reads raw values from provider, validates against model, caches result.
        Raises ConfigurationResolutionFailed if required fields are missing or validation fails.
        """
        if model_cls in self._cache:
            return self._cache[model_cls]

        raw = self._provider.read()
        try:
            instance = model_cls.model_validate(raw)
        except ValidationError as exc:
            errors = [f"{err['loc'][0]}: {err['msg']}" for err in exc.errors()] if exc.errors() else [str(exc)]
            raise ConfigurationResolutionFailed(model_cls.__name__, errors) from exc

        self._cache[model_cls] = instance
        return instance
