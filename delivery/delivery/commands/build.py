from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from rich.console import Console

from ..lib import docker as docker_lib

console = Console()


def build(
    services: list[str],
    tag: str,
    base: Path = Path("."),
    platforms: str = "",
    push: bool = False,
) -> None:
    if not services:
        console.print("[red]No services specified[/red]")
        raise typer.Exit(1)

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()] if platforms else None
    results = docker_lib.buildx_build_parallel(
        services=[(svc, base, base / "agents" / svc / "Dockerfile") for svc in services],
        tag=tag,
        platforms=platform_list,
        push=push,
    )
    for service, result in results.items():
        if result.startswith("ERROR:"):
            console.print(f"[red]{service}: {result}[/red]")
        else:
            console.print(f"[green]{service}: built {result}[/green]")
