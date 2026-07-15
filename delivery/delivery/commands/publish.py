from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..lib import registry as registry_lib
from ..lib.release import record_deployment, create_release

console = Console()


def publish(
    services: list[str],
    tag: str,
    username: str = "aiassistant",
    password: str = "",
) -> None:
    if not services:
        console.print("[red]No services specified[/red]")
        raise typer.Exit(1)
    registry_lib.login("registry.local.test/aiassistant", username, password)
    try:
        for service in services:
            registry_lib.push(service, tag)
            console.print(f"[green]Pushed {service}:{tag}[/green]")
    finally:
        registry_lib.logout("registry.local.test/aiassistant")


def pull(
    services: list[str],
    tag: str,
    username: str = "aiassistant",
    password: str = "",
) -> None:
    if not services:
        console.print("[red]No services specified[/red]")
        raise typer.Exit(1)
    registry_lib.login("registry.local.test/aiassistant", username, password)
    try:
        for service in services:
            registry_lib.pull(service, tag)
            console.print(f"[green]Pulled {service}:{tag}[/green]")
    finally:
        registry_lib.logout("registry.local.test/aiassistant")
