from __future__ import annotations

from rich.console import Console
from rich.table import Table

from vercel_fleet.auth import AuthError, load_team_id, load_token
from vercel_fleet.client import VercelAPIError, VercelClient
from vercel_fleet.store import Store, default_db_path


def render_doctor(console: Console) -> int:
    table = Table(show_header=True, header_style="bold", border_style="dim")
    table.add_column("Check")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="dim")

    rc = 0

    # Token
    try:
        token = load_token()
        table.add_row(
            "Vercel token",
            "[green]✓[/green]",
            f"loaded ({len(token)} chars)",
        )
    except AuthError as e:
        table.add_row("Vercel token", "[red]✗[/red]", str(e))
        rc = 1
        token = None

    # Team
    team = load_team_id()
    table.add_row("Team ID", "[green]✓[/green]", team)

    # API reach
    if token:
        try:
            with VercelClient(token, team) as c:
                projs = c.list_projects()
            table.add_row(
                "API reach",
                "[green]✓[/green]",
                f"{len(projs)} project(s) accessible",
            )
        except VercelAPIError as e:
            table.add_row("API reach", "[red]✗[/red]", str(e))
            rc = 1

    # DB
    db = default_db_path()
    try:
        store = Store(db)
        n = len(store.list_projects())
        last = store.last_sync()
        when = (
            f"last sync stored, {last['projects_synced']} projects"
            if last else "never synced"
        )
        store.close()
        table.add_row(
            "SQLite store",
            "[green]✓[/green]",
            f"{db} — {n} project(s), {when}",
        )
    except Exception as e:
        table.add_row("SQLite store", "[red]✗[/red]", str(e))
        rc = 1

    # Speed Insights — unsupported by public REST as of v0.1
    table.add_row("Speed Insights", "[yellow]N/A[/yellow]", "no public REST endpoint (v2)")

    # Usage / cost
    table.add_row("Usage / cost", "[yellow]N/A[/yellow]", "deferred (v2)")

    console.print(table)
    return rc
