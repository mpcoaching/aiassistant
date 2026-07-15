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
        cmd = ["python", "-m", "pytest", "agentic/src/*/tests", "-v"]
        if coverage:
            cmd.extend(["--cov=agentic/src/workflow-runner", "--cov-report=term-missing"])
    elif kind == "integration":
        cmd = ["python", "-m", "pytest", "infra/ci/", "-v"]
    elif kind == "e2e":
        cmd = ["python", "-m", "pytest", "agentic/src/*/tests", "-v", "-k", "e2e"]
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
