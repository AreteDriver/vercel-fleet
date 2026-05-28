from __future__ import annotations

from rich.console import Console

from vercel_fleet.render import dark_table, fmt_int, header
from vercel_fleet.store import Store


def render_dark(store: Store, console: Console) -> None:
    last = store.last_sync()
    last_ms = last["started_at"] if last else None
    header(console, last_ms)

    projects = store.list_projects()
    table = dark_table()
    count = 0
    for p in projects:
        views = store.total_views(p.id, window="30d")
        if p.has_web_analytics and views > 0:
            continue
        count += 1
        if not p.has_web_analytics:
            analytics = "[red]OFF[/red]"
            reason = "enable Web Analytics in Vercel dashboard"
        else:
            analytics = "[green]ON[/green]"
            reason = "no traffic in 30d"
        table.add_row(
            p.name,
            p.primary_domain or "—",
            analytics,
            fmt_int(views),
            reason,
        )
    console.print(table)
    console.print(f"\n  [yellow]{count} dark project(s)[/yellow]\n")
