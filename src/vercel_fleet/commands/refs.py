from __future__ import annotations

from rich.console import Console
from rich.table import Table

from vercel_fleet.denylist import is_bot
from vercel_fleet.render import fmt_int, header
from vercel_fleet.store import Store


def render_refs(
    store: Store,
    console: Console,
    project: str | None = None,
    include_bots: bool = False,
    window: str = "30d",
) -> int:
    last = store.last_sync()
    last_ms = last["started_at"] if last else None
    header(console, last_ms, window=window)

    if project:
        p = store.get_project_by_name(project)
        if not p:
            console.print(f"[red]No project matching '{project}'.[/red]")
            return 1
        projects = [p]
    else:
        projects = store.list_projects()

    table = Table(
        show_header=True, header_style="bold", border_style="dim", padding=(0, 1)
    )
    table.add_column("Project", style="cyan")
    table.add_column("Hostname", style="white")
    table.add_column("Views", justify="right")
    table.add_column("Tag")

    count = 0
    for p in projects:
        refs = store.get_top(p.id, "referrer_hostname", window=window, limit=10)
        for r in refs:
            bot, _ = is_bot(r.key)
            if bot and not include_bots:
                continue
            tag = "[dim red]bot[/dim red]" if bot else "[green]real[/green]"
            table.add_row(p.name, r.key or "(direct)", fmt_int(r.total), tag)
            count += 1

    console.print(table)
    suffix = "" if include_bots else " (real only — pass --include-bots to see all)"
    console.print(f"\n  {count} referrer(s){suffix}\n")
    return 0
