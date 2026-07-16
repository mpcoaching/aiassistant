from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .base import Provider
from ..models import BuildResult, Package, PublishResult, TestResult


class PythonProvider(Provider):
    def discover(self, package_path: Path) -> dict:
        return {
            "source": package_path / "src",
            "tests": package_path / "tests",
            "pyproject": package_path / "pyproject.toml",
        }

    def build(self, package_path: Path, package: Package) -> BuildResult:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(package_path)],
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
                cmd = [sys.executable, "-m", "pytest", str(package_path / "tests"), "-v"]
            elif kind == "integration":
                cmd = [sys.executable, "-m", "pytest", "platform/tests/integration", "-v", "-k", package.name]
            else:
                return TestResult(success=False, package=package, error=f"Unknown test kind: {kind}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return TestResult(success=False, package=package, output=result.stdout, error=result.stderr)
            return TestResult(success=True, package=package, output=result.stdout)
        except Exception as exc:
            return TestResult(success=False, package=package, error=str(exc))

    def publish(self, package_path: Path, package: Package) -> PublishResult:
        try:
            image = package.docker_image
            cache_image = image.replace(":latest", ":cache").replace(":${GIT_SHA}", ":cache")
            result = subprocess.run(
                [
                    "docker", "buildx", "build",
                    "-t", image,
                    "--cache-from", f"type=registry,ref={cache_image}",
                    "--cache-to", f"type=registry,ref={cache_image},mode=max",
                    str(package_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return PublishResult(success=False, package=package, error=result.stderr)
            return PublishResult(success=True, package=package, image=image)
        except Exception as exc:
            return PublishResult(success=False, package=package, error=str(exc))
