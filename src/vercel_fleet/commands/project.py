from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vercel_fleet.denylist import is_bot
from vercel_fleet.render import (
    fmt_int,
    header,
    project_panel_title,
    relative_time,
    state_style,
)
from vercel_fleet.store import Store


def render_project(store: Store, console: Console, name: str, window: str = "30d") -> int:
    last = store.last_sync()
    last_ms = last["started_at"] if last else None
    header(console, last_ms, window=window)

    p = store.get_project_by_name(name)
    if not p:
        console.print(f"[red]No project matching '{name}'. Try `vercel-fleet overview`.[/red]")
        return 1

    title = project_panel_title(p.name, p.primary_domain)

    views = store.total_views(p.id, window=window)
    paths = store.get_top(p.id, "path", window=window, limit=10)
    refs = store.get_top(p.id, "referrer_hostname", window=window, limit=10)
    countries = store.get_top(p.id, "country", window=window, limit=5)
    devices = store.get_top(p.id, "device_type", window=window, limit=5)
    deploys = store.recent_deployments(project_id=p.id, limit=10)

    facts = Table.grid(padding=(0, 2))
    facts.add_column(style="dim")
    facts.add_column()
    facts.add_row("Framework", p.framework or "—")
    facts.add_row("Web Analytics", "[green]ON[/green]" if p.has_web_analytics else "[red]OFF[/red]")
    facts.add_row("Speed Insights", "[green]ON[/green]" if p.has_speed_insights else "[red]OFF[/red]")
    facts.add_row(f"Views ({window})", f"[bold]{fmt_int(views)}[/bold]")
    facts.add_row("Last Deploy", relative_time(deploys[0].created_at) if deploys else "—")

    console.print(Panel(facts, title=title, border_style="cyan"))

    if paths:
        pt = Table(title="Top Pages", show_header=True, header_style="bold", border_style="dim")
        pt.add_column("Path", style="white")
        pt.add_column("Views", justify="right")
        for r in paths:
            pt.add_row(r.key, fmt_int(r.total))
        console.print(pt)

    if refs:
        rt = Table(title="Referrers", show_header=True, header_style="bold", border_style="dim")
        rt.add_column("Hostname", style="white")
        rt.add_column("Views", justify="right")
        rt.add_column("Tag")
        for r in refs:
            bot, reason = is_bot(r.key)
            tag = "[dim red]bot[/dim red]" if bot else "[green]real[/green]"
            label = r.key if r.key else "(direct)"
            rt.add_row(label, fmt_int(r.total), tag)
        console.print(rt)

    if countries:
        ct = Table(title="Countries", show_header=True, header_style="bold", border_style="dim")
        ct.add_column("Country")
        ct.add_column("Views", justify="right")
        for r in countries:
            ct.add_row(r.key or "—", fmt_int(r.total))
        console.print(ct)

    if devices:
        dt = Table(title="Devices", show_header=True, header_style="bold", border_style="dim")
        dt.add_column("Type")
        dt.add_column("Views", justify="right")
        for r in devices:
            dt.add_row(r.key or "—", fmt_int(r.total))
        console.print(dt)

    if deploys:
        dpt = Table(title="Recent Deploys", show_header=True, header_style="bold", border_style="dim")
        dpt.add_column("When", style="dim")
        dpt.add_column("State", justify="center")
        dpt.add_column("Prod", justify="center")
        dpt.add_column("Commit", overflow="ellipsis", max_width=60)
        for d in deploys:
            dpt.add_row(
                relative_time(d.created_at),
                f"[{state_style(d.state)}]{d.state}[/{state_style(d.state)}]",
                "●" if d.is_production else " ",
                d.commit_message or "—",
            )
        console.print(dpt)

    return 0
