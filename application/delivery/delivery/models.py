from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Package:
    path: Path
    name: str
    version: str
    description: str
    kind: str
    type: str
    provides: list[str] = field(default_factory=list)
    deployable: bool = True
    dockerfile: str = "Dockerfile"
    depends_on: list[str] = field(default_factory=list)
    build_dependencies: list[str] = field(default_factory=list)
    runtime_dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def docker_image(self) -> str:
        return f"registry.local.test/aiassistant/{self.name}:{self.version}"


@dataclass
class BuildResult:
    success: bool
    package: Package
    output: str = ""
    error: str = ""


@dataclass
class TestResult:
    success: bool
    package: Package
    output: str = ""
    error: str = ""


@dataclass
class PublishResult:
    success: bool
    package: Package
    image: str = ""
    error: str = ""


@dataclass
class DeployResult:
    success: bool
    package: Package
    environment: str = ""
    error: str = ""
