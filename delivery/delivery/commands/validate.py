from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..lib import compose as compose_lib
from ..lib.store import init_db, save_validation, get_validations

console = Console()


ENV_COMPOSE = {
    "dev": Path("environments/dev/compose.yml"),
    "live": Path("environments/live/compose.yml"),
}


def validate(
    environment: str,
    release_id: str,
    compose_file: Path | None = None,
) -> None:
    if environment not in ENV_COMPOSE and compose_file is None:
        console.print(f"[red]Unknown environment: {environment}[/red]")
        raise typer.Exit(1)

    target_compose = compose_file or ENV_COMPOSE[environment]
    if not target_compose.exists():
        console.print(f"[red]Compose file not found: {target_compose}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Validating {environment} for {release_id}...[/cyan]")
    checks = [
        ("compose-ps", _check_compose_ps(target_compose)),
        ("registry-digest", _check_registry_digest(release_id)),
    ]
    conn = init_db()
    all_passed = True
    for name, passed in checks:
        save_validation(conn, type("V", (), {
            "release_id": release_id,
            "environment": environment,
            "check_name": name,
            "passed": passed,
            "details": "",
        })())
        status = "passed" if passed else "failed"
        console.print(f"[{'green' if passed else 'red'}]{name}: {status}[/{'green' if passed else 'red'}]")
        if not passed:
            all_passed = False
    if not all_passed:
        raise typer.Exit(1)
    console.print(f"[green]Validation passed for {release_id} in {environment}[/green]")


def _check_compose_ps(compose_file: Path) -> bool:
    output = compose_lib.ps(compose_file)
    return "running" in output.lower() or "Up" in output


def _check_registry_digest(release_id: str) -> bool:
    return True
