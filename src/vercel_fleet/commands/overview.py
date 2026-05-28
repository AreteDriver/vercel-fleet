from __future__ import annotations

from rich.console import Console
from rich.text import Text

from vercel_fleet.denylist import is_bot
from vercel_fleet.render import (
    fmt_int,
    header,
    overview_table,
    relative_time,
    stale_warning,
)
from vercel_fleet.store import Store


def render_overview(store: Store, console: Console, window: str = "30d") -> None:
    last = store.last_sync()
    last_ms = last["started_at"] if last else None
    header(console, last_ms, window=window)

    projects = store.list_projects()
    rows = []
    total_views = 0
    total_real = 0
    dark_count = 0

    for p in projects:
        views = store.total_views(p.id, window=window)
        refs = store.get_top(p.id, "referrer_hostname", window=window, limit=10)
        countries = store.get_top(p.id, "country", window=window, limit=1)
        deploys = store.recent_deployments(project_id=p.id, limit=1)

        real_views = sum(r.total for r in refs if not is_bot(r.key)[0])
        top_real = next((r for r in refs if not is_bot(r.key)[0]), None)
        top_country = countries[0].key if countries else "—"
        last_deploy = relative_time(deploys[0].created_at) if deploys else "—"

        if not p.has_web_analytics or views == 0:
            dark_count += 1
            continue

        total_views += views
        total_real += real_views

        rows.append((
            p.name,
            p.primary_domain or "—",
            views,
            real_views,
            top_real.key if top_real else "—",
            top_country,
            last_deploy,
        ))

    rows.sort(key=lambda r: r[2], reverse=True)

    table = overview_table()
    for r in rows:
        table.add_row(
            r[0], r[1], fmt_int(r[2]), fmt_int(r[3]), r[4], r[5], r[6],
        )
    console.print(table)

    summary = Text()
    summary.append("  TOTAL ", style="bold")
    summary.append(f"{fmt_int(total_views)} views", style="bold cyan")
    summary.append(f"  ({fmt_int(total_real)} real)", style="green")
    summary.append(f"   DARK: {dark_count} projects", style="yellow")
    console.print(summary)

    warning = stale_warning(last_ms)
    if warning:
        console.print(f"[yellow]  ⚠ {warning}[/yellow]")
