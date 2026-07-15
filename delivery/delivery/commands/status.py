from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..lib.store import init_db, get_release, get_deployments, get_validations

console = Console()


def status(release_id: str | None = None, state_dir: Path = Path("delivery/state")) -> None:
    conn = init_db()
    if release_id:
        releases = [get_release(conn, release_id)]
    else:
        import sqlite3
        rows = conn.execute("SELECT id FROM releases ORDER BY build_timestamp DESC").fetchall()
        releases = [get_release(conn, row["id"]) for row in rows]

    table = Table(title="Releases")
    table.add_column("Release")
    table.add_column("Built")
    table.add_column("Environments")
    for release in releases:
        if not release:
            continue
        envs = ", ".join(release.environments.keys()) if release.environments else "-"
        table.add_row(release.id, release.build_timestamp, envs)
    console.print(table)

    for release in releases:
        if not release:
            continue
        deployments = get_deployments(conn, release.id)
        if deployments:
            dtable = Table(title=f"Deployments for {release.id}")
            dtable.add_column("Env")
            dtable.add_column("Status")
            dtable.add_column("Deployed At")
            for d in deployments:
                dtable.add_row(d.environment, d.status, d.deployed_at)
            console.print(dtable)
