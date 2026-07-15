from __future__ import annotations

import subprocess
from pathlib import Path

from .base import Provider
from ..models import BuildResult, Package, PublishResult, TestResult


class TypeScriptProvider(Provider):
    def discover(self, package_path: Path) -> dict:
        return {
            "source": package_path / "src",
            "tests": package_path / "tests",
            "package_json": package_path / "package.json",
        }

    def build(self, package_path: Path, package: Package) -> BuildResult:
        try:
            result = subprocess.run(
                ["npm", "install"],
                cwd=package_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return BuildResult(success=False, package=package, error=result.stderr)
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=package_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return BuildResult(success=False, package=package, error=result.stderr)
            return BuildResult(success=True, package=package, output=result.stdout)
        except Exception as exc:
            return BuildResult(success=False, package=package, error=str(exc))

    def test(self, package_path: Path, package: Package, kind: str = "unit") -> TestResult:
        try:
            if kind == "unit":
                cmd = ["npm", "run", "test"]
            elif kind == "e2e":
                cmd = ["npm", "run", "test:e2e"]
            else:
                return TestResult(success=False, package=package, error=f"Unknown test kind: {kind}")
            result = subprocess.run(cmd, cwd=package_path, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return TestResult(success=False, package=package, output=result.stdout, error=result.stderr)
            return TestResult(success=True, package=package, output=result.stdout)
        except Exception as exc:
            return TestResult(success=False, package=package, error=str(exc))

    def publish(self, package_path: Path, package: Package) -> PublishResult:
        try:
            result = subprocess.run(
                ["docker", "build", "-t", package.docker_image, str(package_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return PublishResult(success=False, package=package, error=result.stderr)
            return PublishResult(success=True, package=package, image=package.docker_image)
        except Exception as exc:
            return PublishResult(success=False, package=package, error=str(exc))
