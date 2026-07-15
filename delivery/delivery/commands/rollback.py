from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..lib import compose as compose_lib

console = Console()


ENV_COMPOSE = {
    "dev": Path("environments/dev/compose.yml"),
    "live": Path("environments/live/compose.yml"),
}


def rollback(environment: str, compose_file: Path | None = None) -> None:
    if environment not in ENV_COMPOSE and compose_file is None:
        console.print(f"[red]Unknown environment: {environment}[/red]")
        raise typer.Exit(1)
    target_compose = compose_file or ENV_COMPOSE[environment]
    if not target_compose.exists():
        console.print(f"[red]Compose file not found: {target_compose}[/red]")
        raise typer.Exit(1)
    console.print(f"[cyan]Rolling back {environment}...[/cyan]")
    compose_lib.rollback(target_compose)
    console.print(f"[green]Rolled back {environment}[/green]")
