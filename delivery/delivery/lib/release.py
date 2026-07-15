from __future__ import annotations

import hashlib
import json
import os
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import Release, Deployment, ValidationResult


DB_PATH = Path(os.environ.get("DELIVERY_STATE_DIR", "delivery/state")) / "delivery.db"


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def build_release_id(git_sha: str) -> str:
    return git_sha


def create_release(
    git_sha: str,
    image_digests: dict[str, str],
    test_results: dict[str, str],
    compose_file: str = "environments/dev/compose.yml",
) -> Release:
    release = Release(
        id=build_release_id(git_sha),
        image_digests=image_digests,
        test_results=test_results,
        migration_version=datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
        build_timestamp=now_iso(),
        builder="gitea-runner",
        environments={},
    )
    return release


def record_deployment(release: Release, environment: str, compose_file: str) -> Deployment:
    deployment = Deployment(
        release_id=release.id,
        environment=environment,
        status="deployed",
        deployed_at=now_iso(),
        compose_file=compose_file,
    )
    if environment not in release.environments:
        release.environments[environment] = {}
    release.environments[environment].update(
        {
            "status": deployment.status,
            "deployed_at": deployment.deployed_at,
            "compose_file": deployment.compose_file,
        }
    )
    return deployment


def backup(db_path: Path = DB_PATH, output: Optional[Path] = None) -> Path:
    if output is None:
        output = Path("delivery/state/backups") / f"backup-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.tar.gz"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as tar:
        tar.add(db_path, arcname=db_path.name)
    manifest = {
        "backup_timestamp": now_iso(),
        "db": str(db_path.name),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    manifest_path = output.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return output


def restore(archive: Path, db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        member = next((m for m in tar.getmembers() if m.name == db_path.name), None)
        if member is None:
            raise RuntimeError(f"Archive does not contain {db_path.name}")
        tar.extract(member, path=db_path.parent)
