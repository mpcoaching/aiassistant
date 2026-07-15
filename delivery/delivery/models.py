from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Release:
    id: str
    image_digests: dict[str, str] = field(default_factory=dict)
    test_results: dict[str, str] = field(default_factory=dict)
    migration_version: str = ""
    build_timestamp: str = ""
    builder: str = "gitea-runner"
    environments: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "image_digests": self.image_digests,
            "test_results": self.test_results,
            "migration_version": self.migration_version,
            "build_timestamp": self.build_timestamp,
            "builder": self.builder,
            "environments": self.environments,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Release":
        return cls(
            id=data["id"],
            image_digests=data.get("image_digests", {}),
            test_results=data.get("test_results", {}),
            migration_version=data.get("migration_version", ""),
            build_timestamp=data.get("build_timestamp", ""),
            builder=data.get("builder", "gitea-runner"),
            environments=data.get("environments", {}),
        )

@dataclass
class Deployment:
    release_id: str
    environment: str
    status: str = "pending"
    deployed_at: str = ""
    compose_file: str = ""

    def to_dict(self) -> dict:
        return {
            "release_id": self.release_id,
            "environment": self.environment,
            "status": self.status,
            "deployed_at": self.deployed_at,
            "compose_file": self.compose_file,
        }

@dataclass
class ValidationResult:
    release_id: str
    environment: str
    check_name: str
    passed: bool
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "release_id": self.release_id,
            "environment": self.environment,
            "check_name": self.check_name,
            "passed": self.passed,
            "details": self.details,
        }
