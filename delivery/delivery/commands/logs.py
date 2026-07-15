from __future__ import annotations

import typer
from rich.console import Console

from ..lib import compose as compose_lib

console = Console()


def logs(
    environment: str,
    service: str | None = None,
    follow: bool = False,
    compose_file: str | None = None,
) -> None:
    target = compose_file or f"environments/{environment}/compose.yml"
    output = compose_lib.logs(Path(target), service, follow)
    if output:
        console.print(output)
