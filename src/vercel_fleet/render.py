from __future__ import annotations

import time
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table
from rich.text import Text

SPARK = "▁▂▃▄▅▆▇█"


def sparkline(values: list[int], width: int = 8) -> str:
    if not values:
        return " " * width
    vals = values[-width:]
    while len(vals) < width:
        vals.insert(0, 0)
    peak = max(vals)
    if peak == 0:
        return SPARK[0] * width
    return "".join(SPARK[min(len(SPARK) - 1, int(v / peak * (len(SPARK) - 1)))] for v in vals)


def relative_time(ts_ms: int) -> str:
    if ts_ms <= 0:
        return "—"
    now = time.time() * 1000
    delta = now - ts_ms
    if delta < 0:
        return "just now"
    secs = delta / 1000
    if secs < 60:
        return f"{int(secs)}s ago"
    if secs < 3600:
        return f"{int(secs/60)}m ago"
    if secs < 86400:
        return f"{int(secs/3600)}h ago"
    days = int(secs / 86400)
    return f"{days}d ago"


def state_style(state: str) -> str:
    return {
        "READY": "green",
        "ERROR": "red",
        "BUILDING": "yellow",
        "QUEUED": "yellow",
        "CANCELED": "dim",
        "INITIALIZING": "yellow",
    }.get(state, "white")


def header(console: Console, last_sync_ms: int | None, window: str = "30d") -> None:
    when = "never" if not last_sync_ms else relative_time(last_sync_ms)
    sync_dt = (
        datetime.fromtimestamp(last_sync_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if last_sync_ms else "never"
    )
    bar = "─" * 78
    console.print(f"[dim]{bar}[/dim]")
    title = Text()
    title.append("  ARETE FLEET ", style="bold")
    title.append(f"— window {window} — last sync ", style="dim")
    title.append(when, style="cyan" if when != "never" else "red")
    title.append(f"  ({sync_dt})", style="dim")
    console.print(title)
    console.print(f"[dim]{bar}[/dim]")


def stale_warning(last_sync_ms: int | None, threshold_min: int = 30) -> str | None:
    if not last_sync_ms:
        return "no sync data yet — run `vercel-fleet sync`"
    age_min = (time.time() * 1000 - last_sync_ms) / 1000 / 60
    if age_min > threshold_min:
        return f"data is {int(age_min)}m old — consider `vercel-fleet sync`"
    return None


def fmt_int(n: int) -> str:
    return f"{n:,}"


def overview_table() -> Table:
    table = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Project", style="white")
    table.add_column("Domain", style="cyan")
    table.add_column("Views", justify="right", style="bold")
    table.add_column("Real", justify="right", style="green")
    table.add_column("Top Real Referrer", style="white")
    table.add_column("Country", style="dim")
    table.add_column("Last Deploy", style="dim")
    return table


def deploys_table() -> Table:
    table = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("When", style="dim")
    table.add_column("Project", style="cyan")
    table.add_column("State", justify="center")
    table.add_column("Prod", justify="center")
    table.add_column("Commit", style="white", overflow="ellipsis", max_width=60)
    return table


def dark_table() -> Table:
    table = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Project", style="white")
    table.add_column("Domain", style="cyan")
    table.add_column("Analytics", justify="center")
    table.add_column("Views 30d", justify="right")
    table.add_column("Reason", style="yellow")
    return table


def project_panel_title(name: str, domain: str | None) -> Text:
    t = Text()
    t.append(name, style="bold")
    if domain:
        t.append(f"   {domain}", style="cyan")
    return t
