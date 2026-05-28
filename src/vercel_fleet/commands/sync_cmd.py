from __future__ import annotations

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from vercel_fleet.auth import load_team_id, load_token
from vercel_fleet.client import VercelClient
from vercel_fleet.store import Store
from vercel_fleet.sync import run_sync


def run(console: Console, quiet: bool = False) -> int:
    token = load_token()
    team = load_team_id()

    with Store() as store, VercelClient(token, team) as client:
        if quiet:
            result = run_sync(client, store)
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Syncing Vercel fleet…", total=None)

                def on_progress(name: str) -> None:
                    progress.update(task, description=f"Syncing… {name}")

                result = run_sync(client, store, on_progress=on_progress)

    if not quiet:
        console.print(
            f"[green]✓[/green] synced {result.projects_synced} project(s) "
            f"in {result.duration_ms}ms "
            f"({result.api_calls} API calls)"
        )
        if result.errors:
            console.print(f"[yellow]⚠ {len(result.errors)} error(s):[/yellow]")
            for e in result.errors[:10]:
                console.print(f"  [dim]· {e}[/dim]")
    return 0 if not result.errors else 0  # non-fatal partial errors
