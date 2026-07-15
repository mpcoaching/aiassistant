import sqlite3
import os
from pathlib import Path
from typing import Optional
from ..models import Release, Deployment, ValidationResult

DB_PATH = Path(os.environ.get("DELIVERY_STATE_DIR", "delivery/state")) / "delivery.db"


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS releases (
            id TEXT PRIMARY KEY,
            image_digests TEXT,
            test_results TEXT,
            migration_version TEXT,
            build_timestamp TEXT,
            builder TEXT,
            environments TEXT
        );
        CREATE TABLE IF NOT EXISTS deployments (
            release_id TEXT,
            environment TEXT,
            status TEXT,
            deployed_at TEXT,
            compose_file TEXT,
            PRIMARY KEY (release_id, environment)
        );
        CREATE TABLE IF NOT EXISTS validation_results (
            release_id TEXT,
            environment TEXT,
            check_name TEXT,
            passed INTEGER,
            details TEXT,
            PRIMARY KEY (release_id, environment, check_name)
        );
    """)
    conn.commit()
    return conn


def save_release(conn: sqlite3.Connection, release: Release) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO releases VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            release.id,
            sqlite3.JSON(release.image_digests),
            sqlite3.JSON(release.test_results),
            release.migration_version,
            release.build_timestamp,
            release.builder,
            sqlite3.JSON(release.environments),
        ),
    )
    conn.commit()


def get_release(conn: sqlite3.Connection, release_id: str) -> Optional[Release]:
    row = conn.execute("SELECT * FROM releases WHERE id = ?", (release_id,)).fetchone()
    if not row:
        return None
    import json
    return Release(
        id=row["id"],
        image_digests=json.loads(row["image_digests"] or "{}"),
        test_results=json.loads(row["test_results"] or "{}"),
        migration_version=row["migration_version"] or "",
        build_timestamp=row["build_timestamp"] or "",
        builder=row["builder"] or "gitea-runner",
        environments=json.loads(row["environments"] or "{}"),
    )


def save_deployment(conn: sqlite3.Connection, deployment: Deployment) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO deployments VALUES (?, ?, ?, ?, ?)",
        (
            deployment.release_id,
            deployment.environment,
            deployment.status,
            deployment.deployed_at,
            deployment.compose_file,
        ),
    )
    conn.commit()


def get_deployments(conn: sqlite3.Connection, release_id: str) -> list[Deployment]:
    rows = conn.execute(
        "SELECT * FROM deployments WHERE release_id = ?", (release_id,)
    ).fetchall()
    return [
        Deployment(
            release_id=row["release_id"],
            environment=row["environment"],
            status=row["status"],
            deployed_at=row["deployed_at"],
            compose_file=row["compose_file"],
        )
        for row in rows
    ]


def save_validation(conn: sqlite3.Connection, result: ValidationResult) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO validation_results VALUES (?, ?, ?, ?, ?)",
        (
            result.release_id,
            result.environment,
            result.check_name,
            1 if result.passed else 0,
            result.details,
        ),
    )
    conn.commit()


def get_validations(conn: sqlite3.Connection, release_id: str, environment: str) -> list[ValidationResult]:
    rows = conn.execute(
        "SELECT * FROM validation_results WHERE release_id = ? AND environment = ?",
        (release_id, environment),
    ).fetchall()
    return [
        ValidationResult(
            release_id=row["release_id"],
            environment=row["environment"],
            check_name=row["check_name"],
            passed=bool(row["passed"]),
            details=row["details"],
        )
        for row in rows
    ]
