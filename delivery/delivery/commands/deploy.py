from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..lib import compose as compose_lib
from ..lib.release import record_deployment
from ..lib.store import init_db, save_deployment, save_release

console = Console()


ENV_COMPOSE = {
    "dev": Path("environments/dev/compose.yml"),
    "live": Path("environments/live/compose.yml"),
}


def deploy(
    environment: str,
    release_id: str,
    compose_file: Path | None = None,
    state_dir: Path = Path("delivery/state"),
) -> None:
    if environment not in ENV_COMPOSE and compose_file is None:
        console.print(f"[red]Unknown environment: {environment}[/red]")
        raise typer.Exit(1)

    target_compose = compose_file or ENV_COMPOSE[environment]
    if not target_compose.exists():
        console.print(f"[red]Compose file not found: {target_compose}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Deploying {release_id} to {environment}...[/cyan]")
    compose_lib.deploy(target_compose)

    conn = init_db()
    release = save_release(conn, type("R", (), {"id": release_id})())
    deployment = record_deployment(release, environment, str(target_compose))
    save_deployment(conn, deployment)
    console.print(f"[green]Deployed {release_id} to {environment}[/green]")
