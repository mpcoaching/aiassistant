from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..lib.release import backup as do_backup

console = Console()


def backup(
    output: Path = Path("delivery/state/backups") / "backup.tar.gz",
    state_dir: Path = Path("delivery/state"),
) -> None:
    path = do_backup(output=output)
    console.print(f"[green]Backup written to {path}[/green]")
