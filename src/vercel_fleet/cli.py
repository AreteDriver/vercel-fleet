from __future__ import annotations

import typer
from rich.console import Console

from vercel_fleet import __version__
from vercel_fleet.commands.dark import render_dark
from vercel_fleet.commands.deploys import render_deploys
from vercel_fleet.commands.doctor import render_doctor
from vercel_fleet.commands.install_timer import install as install_timer_cmd
from vercel_fleet.commands.overview import render_overview
from vercel_fleet.commands.project import render_project
from vercel_fleet.commands.refs import render_refs
from vercel_fleet.commands.sync_cmd import run as run_sync_cmd
from vercel_fleet.denylist import BOT_REFERRERS
from vercel_fleet.store import Store

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Cross-project Vercel analytics rollup.",
)
console = Console()


def _version_cb(value: bool) -> None:
    if value:
        console.print(f"vercel-fleet {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", callback=_version_cb, is_eager=True
    ),
) -> None:
    pass


@app.command()
def overview(window: str = typer.Option("30d", "--window")) -> None:
    """30-day cross-project rollup."""
    with Store() as store:
        render_overview(store, console, window=window)


@app.command()
def dark() -> None:
    """List projects with analytics off or zero traffic."""
    with Store() as store:
        render_dark(store, console)


@app.command()
def deploys(
    since: str | None = typer.Option(None, "--since"),
    state: str | None = typer.Option(None, "--state"),
    limit: int = typer.Option(30, "--limit"),
) -> None:
    """Fleet-wide deployments."""
    with Store() as store:
        render_deploys(store, console, since=since, state=state, limit=limit)


@app.command()
def project(name: str, window: str = typer.Option("30d", "--window")) -> None:
    """Drill into one project."""
    with Store() as store:
        rc = render_project(store, console, name, window=window)
    raise typer.Exit(rc)


@app.command()
def refs(
    project: str | None = typer.Option(None, "--project"),
    include_bots: bool = typer.Option(False, "--include-bots"),
    window: str = typer.Option("30d", "--window"),
) -> None:
    """List referrer hostnames (real-only by default)."""
    with Store() as store:
        rc = render_refs(store, console, project=project, include_bots=include_bots, window=window)
    raise typer.Exit(rc)


@app.command()
def denylist() -> None:
    """Show the bot referrer denylist."""
    console.print("[bold]Bot referrer denylist[/bold]\n")
    for host, reason in BOT_REFERRERS.items():
        console.print(f"  [cyan]{host}[/cyan] — {reason}")


@app.command()
def doctor() -> None:
    """Diagnose token, API reach, and DB state."""
    rc = render_doctor(console)
    raise typer.Exit(rc)


@app.command()
def sync(quiet: bool = typer.Option(False, "--quiet")) -> None:
    """Pull fresh data from Vercel API and upsert to SQLite."""
    rc = run_sync_cmd(console, quiet=quiet)
    raise typer.Exit(rc)


@app.command(name="install-timer")
def install_timer() -> None:
    """Install + enable the systemd-user timer that runs `sync` every 15 min."""
    rc = install_timer_cmd(console)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
