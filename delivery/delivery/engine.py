from __future__ import annotations

from pathlib import Path

from .models import BuildResult, DeployResult, Package, PublishResult, TestResult
from .package_registry import PackageRegistry
from .provider_registry import ProviderRegistry


class ExecutionEngine:
    def __init__(self, package_registry: PackageRegistry, provider_registry: ProviderRegistry) -> None:
        self.package_registry = package_registry
        self.provider_registry = provider_registry

    def build(self, package_names: list[str]) -> dict[str, BuildResult]:
        packages = self.package_registry.discover()
        results: dict[str, BuildResult] = {}
        for name in package_names:
            package = self.package_registry.get(name, packages)
            if not package:
                results[name] = BuildResult(success=False, package=Package(path=Path("."), name=name, version="", description="", kind="", type=""), error="Package not found")
                continue
            provider = self.provider_registry.resolve(package)
            results[name] = provider.build(package.path, package)
        return results

    def test(self, package_names: list[str], kind: str = "unit") -> dict[str, TestResult]:
        packages = self.package_registry.discover()
        results: dict[str, TestResult] = {}
        for name in package_names:
            package = self.package_registry.get(name, packages)
            if not package:
                results[name] = TestResult(success=False, package=Package(path=Path("."), name=name, version="", description="", kind="", type=""), error="Package not found")
                continue
            provider = self.provider_registry.resolve(package)
            results[name] = provider.test(package.path, package, kind)
        return results

    def publish(self, package_names: list[str]) -> dict[str, PublishResult]:
        packages = self.package_registry.discover()
        results: dict[str, PublishResult] = {}
        for name in package_names:
            package = self.package_registry.get(name, packages)
            if not package:
                results[name] = PublishResult(success=False, package=Package(path=Path("."), name=name, version="", description="", kind="", type=""), error="Package not found")
                continue
            provider = self.provider_registry.resolve(package)
            results[name] = provider.publish(package.path, package)
        return results

    def deploy(self, environment: str, package_names: list[str]) -> dict[str, DeployResult]:
        # Placeholder: deploy would invoke docker compose per package
        results: dict[str, DeployResult] = {}
        packages = self.package_registry.discover()
        for name in package_names:
            package = self.package_registry.get(name, packages)
            if not package:
                results[name] = DeployResult(success=False, package=Package(path=Path("."), name=name, version="", description="", kind="", type=""), environment=environment, error="Package not found")
                continue
            results[name] = DeployResult(success=True, package=package, environment=environment)
        return results
