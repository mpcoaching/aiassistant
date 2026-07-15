from __future__ import annotations

import typer
from rich.console import Console

from .build import build as build_cmd
from .test import test as test_cmd
from .publish import publish as publish_cmd
from .deploy import deploy as deploy_cmd
from .validate import validate as validate_cmd
from .status import status as status_cmd
from .doctor import doctor as doctor_cmd
from .promote import promote as promote_cmd
from .rollback import rollback as rollback_cmd
from .backup import backup as backup_cmd
from .restore import restore as restore_cmd
from .logs import logs as logs_cmd

app = typer.Typer(help="Capability-oriented delivery CLI for Gitea Actions")
app.command()(build_cmd)
app.command()(test_cmd)
app.command()(publish_cmd)
app.command()(deploy_cmd)
app.command()(validate_cmd)
app.command()(status_cmd)
app.command()(doctor_cmd)
app.command()(promote_cmd)
app.command()(rollback_cmd)
app.command()(backup_cmd)
app.command()(restore_cmd)
app.command()(logs_cmd)


def app_main() -> None:
    app()
