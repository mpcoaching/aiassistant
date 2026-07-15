from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..lib.release import restore as do_restore

console = Console()


def restore(archive: Path, state_dir: Path = Path("delivery/state")) -> None:
    do_restore(archive)
    console.print(f"[green]Restored from {archive}[/green]")
