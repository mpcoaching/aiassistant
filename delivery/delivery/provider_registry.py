from __future__ import annotations

from typing import TYPE_CHECKING

from .models import BuildResult, Package, PublishResult, TestResult

if TYPE_CHECKING:
    from .providers.base import Provider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, package_type: str, provider: Provider) -> None:
        self._providers[package_type] = provider

    def resolve(self, package: Package) -> Provider:
        if package.type not in self._providers:
            raise ValueError(f"No provider registered for package type: {package.type}")
        return self._providers[package.type]
