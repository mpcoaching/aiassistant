from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from .engine import ExecutionEngine
from .package_registry import PackageRegistry
from .provider_registry import ProviderRegistry
from .providers.python import PythonProvider
from .providers.typescript import TypeScriptProvider

app = typer.Typer(help="Package-based delivery engine")
console = Console()

package_registry = PackageRegistry()
provider_registry = ProviderRegistry()
provider_registry.register("python", PythonProvider())
provider_registry.register("typescript", TypeScriptProvider())
engine = ExecutionEngine(package_registry, provider_registry)


@app.command()
def discover(format: str = "table") -> None:
    packages = package_registry.discover()
    if format == "json":
        console.print(json.dumps([{"name": p.name, "version": p.version, "type": p.type} for p in packages]))
    else:
        table = Table(title="Packages")
        table.add_column("Name")
        table.add_column("Version")
        table.add_column("Type")
        table.add_column("Kind")
        table.add_column("Deployable")
        for package in packages:
            table.add_row(package.name, package.version, package.type, package.kind, str(package.deployable))
        console.print(table)


def _resolve_packages(names: list[str]) -> list[str]:
    if "all" in names:
        return [p.name for p in package_registry.discover()]
    return names


@app.command()
def build(packages: list[str]) -> None:
    names = _resolve_packages(packages)
    results = engine.build(names)
    for name, result in results.items():
        if result.success:
            console.print(f"[green]{name}: built[/green]")
        else:
            console.print(f"[red]{name}: {result.error}[/red]")


@app.command()
def test(
    packages: list[str] = typer.Argument(..., help="Package names or 'all'"),
    kind: str = "unit",
) -> None:
    names = _resolve_packages(packages)
    results = engine.test(names, kind)
    for name, result in results.items():
        if result.success:
            console.print(f"[green]{name}: {kind} tests passed[/green]")
        else:
            console.print(f"[red]{name}: {kind} tests failed[/red]")
            if result.error:
                console.print(result.error)


@app.command()
def publish(packages: list[str]) -> None:
    names = _resolve_packages(packages)
    results = engine.publish(names)
    for name, result in results.items():
        if result.success:
            console.print(f"[green]{name}: published {result.image}[/green]")
        else:
            console.print(f"[red]{name}: {result.error}[/red]")


@app.command()
def deploy(
    environment: str = typer.Argument(..., help="Environment name"),
    packages: list[str] = typer.Argument(..., help="Package names or 'all'"),
) -> None:
    names = _resolve_packages(packages)
    results = engine.deploy(environment, names)
    for name, result in results.items():
        if result.success:
            console.print(f"[green]{name}: deployed to {environment}[/green]")
        else:
            console.print(f"[red]{name}: {result.error}[/red]")


if __name__ == "__main__":
    app()
