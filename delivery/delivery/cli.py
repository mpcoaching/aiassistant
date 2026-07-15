from typer import Typer

app = Typer(help="Capability-oriented delivery CLI for Gitea Actions")

from delivery.commands import (  # noqa: E402
    backup,
    build,
    doctor,
    deploy,
    logs,
    promote,
    publish,
    restore,
    rollback,
    status,
    test,
    validate,
)

app.command()(build.build)
app.command()(test.test)
app.command()(publish.publish)
app.command()(deploy.deploy)
app.command()(validate.validate)
app.command()(status.status)
app.command()(doctor.doctor)
app.command()(promote.promote)
app.command()(rollback.rollback)
app.command()(backup.backup)
app.command()(restore.restore)
app.command()(logs.logs)

__all__ = ["app"]
