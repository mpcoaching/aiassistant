from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import BuildResult, Package, PublishResult, TestResult


class Provider(ABC):
    @abstractmethod
    def discover(self, package_path: Path) -> dict:
        """Scan package directory and return source/test locations."""

    @abstractmethod
    def build(self, package_path: Path, package: Package) -> BuildResult:
        """Execute language-specific build."""

    @abstractmethod
    def test(self, package_path: Path, package: Package, kind: str = "unit") -> TestResult:
        """Execute language-specific tests."""

    @abstractmethod
    def publish(self, package_path: Path, package: Package) -> PublishResult:
        """Produce publishable artifact (image, binary, etc.)."""
