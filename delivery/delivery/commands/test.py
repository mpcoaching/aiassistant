from __future__ import annotations

import subprocess

import typer
from rich.console import Console

console = Console()


def test(
    kind: str,
    coverage: bool = False,
    fail_fast: bool = False,
) -> None:
    if kind == "unit":
        cmd = ["python", "-m", "pytest", "agents/*/tests", "-v"]
        if coverage:
            cmd.extend(["--cov=agents", "--cov-report=term-missing"])
    elif kind == "integration":
        cmd = ["bash", "cicd/scripts/integration-tests.sh"]
    elif kind == "e2e":
        cmd = ["bash", "cicd/scripts/integration-tests.sh"]
    else:
        console.print(f"[red]Unknown test kind: {kind}[/red]")
        raise typer.Exit(1)
    if fail_fast:
        cmd.append("-x")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        console.print(f"[red]Tests failed: {' '.join(cmd)}[/red]")
        raise typer.Exit(result.returncode)
    console.print(f"[green]{kind} tests passed[/green]")
