from __future__ import annotations

from pathlib import Path

import yaml

from .models import Package


class PackageRegistry:
    def discover(self, root: Path = Path("packages")) -> list[Package]:
        packages = []
        for package_yaml in sorted(root.glob("*/package.yaml")):
            try:
                data = yaml.safe_load(package_yaml.read_text())
                packages.append(
                    Package(
                        path=package_yaml.parent,
                        name=data["name"],
                        version=data.get("version", "0.1.0"),
                        description=data.get("description", ""),
                        kind=data.get("kind", "service"),
                        type=data.get("type", "unknown"),
                        provides=data.get("provides", []),
                        deployable=data.get("deployable", True),
                        dockerfile=data.get("dockerfile", "Dockerfile"),
                        depends_on=data.get("depends_on", []),
                        build_dependencies=data.get("build_dependencies", []),
                        runtime_dependencies=data.get("runtime_dependencies", []),
                        tags=data.get("tags", []),
                        raw=data,
                    )
                )
            except Exception as exc:
                raise RuntimeError(f"Failed to parse {package_yaml}: {exc}") from exc
        return packages

    def get(self, name: str, packages: list[Package] | None = None) -> Package | None:
        if packages is None:
            packages = self.discover()
        for package in packages:
            if package.name == name:
                return package
        return None

    def list(
        self,
        kind: str | None = None,
        tags: list[str] | None = None,
        packages: list[Package] | None = None,
    ) -> list[Package]:
        if packages is None:
            packages = self.discover()
        result = packages
        if kind:
            result = [p for p in result if p.kind == kind]
        if tags:
            result = [p for p in result if any(t in p.tags for t in tags)]
        return result
