from __future__ import annotations

import time

from rich.console import Console

from vercel_fleet.render import deploys_table, header, relative_time, state_style
from vercel_fleet.store import Store


def parse_since(raw: str) -> int | None:
    if not raw:
        return None
    raw = raw.strip().lower()
    if raw.endswith("d"):
        days = int(raw[:-1])
        return int((time.time() - days * 86400) * 1000)
    if raw.endswith("h"):
        hours = int(raw[:-1])
        return int((time.time() - hours * 3600) * 1000)
    if raw.endswith("m"):
        mins = int(raw[:-1])
        return int((time.time() - mins * 60) * 1000)
    raise ValueError(f"Unsupported --since value: {raw}")


def render_deploys(
    store: Store,
    console: Console,
    since: str | None = None,
    state: str | None = None,
    limit: int = 30,
) -> None:
    last = store.last_sync()
    last_ms = last["started_at"] if last else None
    header(console, last_ms)

    since_ms = parse_since(since) if since else None
    deploys = store.recent_deployments(limit=limit * 4, since=since_ms)

    if state:
        deploys = [d for d in deploys if d.state.upper() == state.upper()]

    projects = {p.id: p for p in store.list_projects()}

    table = deploys_table()
    for d in deploys[:limit]:
        proj = projects.get(d.project_id)
        proj_name = proj.name if proj else d.project_id[:12]
        prod_mark = "●" if d.is_production else " "
        table.add_row(
            relative_time(d.created_at),
            proj_name,
            f"[{state_style(d.state)}]{d.state}[/{state_style(d.state)}]",
            prod_mark,
            d.commit_message or "—",
        )
    console.print(table)
    console.print(f"\n  Showing {min(len(deploys), limit)} deploy(s)\n")
