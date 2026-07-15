from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..lib import compose as compose_lib
from ..lib.store import init_db, get_release, save_deployment
from ..lib.release import record_deployment

console = Console()


ENV_COMPOSE = {
    "dev": Path("environments/dev/compose.yml"),
    "live": Path("environments/live/compose.yml"),
}


def promote(
    source_env: str,
    target_env: str,
    release_id: str,
    compose_file: Path | None = None,
) -> None:
    if target_env not in ENV_COMPOSE and compose_file is None:
        console.print(f"[red]Unknown target environment: {target_env}[/red]")
        raise typer.Exit(1)

    target_compose = compose_file or ENV_COMPOSE[target_env]
    if not target_compose.exists():
        console.print(f"[red]Compose file not found: {target_compose}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Promoting {release_id} from {source_env} to {target_env}...[/cyan]")
    compose_lib.deploy(target_compose)

    conn = init_db()
    release = get_release(conn, release_id) or type("R", (), {"id": release_id, "environments": {}})()
    deployment = record_deployment(release, target_env, str(target_compose))
    save_deployment(conn, deployment)
    console.print(f"[green]Promoted {release_id} to {target_env}[/green]")
