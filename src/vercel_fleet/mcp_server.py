"""MCP stdio server for vercel-fleet.

Exposes the same data the CLI renders, as JSON-returning tools. Backed
by the same SQLite store; the cron `sync` keeps it fresh.

Install: pip install vercel-fleet[mcp]
Register with Claude Code:
    claude mcp add vercel-fleet -- vercel-fleet-mcp
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from vercel_fleet.anomalies import detect
from vercel_fleet.auth import load_team_id, load_token
from vercel_fleet.client import VercelClient
from vercel_fleet.denylist import BOT_REFERRERS, is_bot
from vercel_fleet.store import Store
from vercel_fleet.sync import run_sync


class MCPNotInstalledError(RuntimeError):
    pass


def _project_to_dict(p, store: Store, window: str = "30d") -> dict[str, Any]:
    views = store.total_views(p.id, window=window)
    refs = store.get_top(p.id, "referrer_hostname", window=window, limit=10)
    real_refs = [
        {"hostname": r.key, "views": r.total} for r in refs if not is_bot(r.key)[0]
    ]
    deploys = store.recent_deployments(project_id=p.id, limit=1)
    return {
        "id": p.id,
        "name": p.name,
        "domain": p.primary_domain,
        "framework": p.framework,
        "has_web_analytics": p.has_web_analytics,
        "has_speed_insights": p.has_speed_insights,
        "views_30d": views,
        "real_referrer_views": sum(r["views"] for r in real_refs),
        "top_real_referrer": real_refs[0]["hostname"] if real_refs else None,
        "last_deploy_at_ms": deploys[0].created_at if deploys else None,
        "last_deploy_state": deploys[0].state if deploys else None,
        "is_dark": not p.has_web_analytics or views == 0,
    }


def overview_data(store: Store, window: str = "30d") -> dict[str, Any]:
    last = store.last_sync()
    projects = [_project_to_dict(p, store, window) for p in store.list_projects()]
    visible = [p for p in projects if not p["is_dark"]]
    visible.sort(key=lambda p: p["views_30d"], reverse=True)
    dark = [p for p in projects if p["is_dark"]]
    anomalies = [
        {"kind": a.kind, "project": a.project, "detail": a.detail}
        for a in detect(store)
    ]
    return {
        "synced_at_ms": last["started_at"] if last else None,
        "window": window,
        "totals": {
            "projects": len(projects),
            "live": len(visible),
            "dark": len(dark),
            "views": sum(p["views_30d"] for p in visible),
            "real_referrer_views": sum(p["real_referrer_views"] for p in visible),
        },
        "projects": visible,
        "anomalies": anomalies,
    }


def project_data(store: Store, name: str, window: str = "30d") -> dict[str, Any]:
    p = store.get_project_by_name(name)
    if not p:
        return {"error": f"No project matching '{name}'"}
    paths = store.get_top(p.id, "path", window=window, limit=10)
    refs = store.get_top(p.id, "referrer_hostname", window=window, limit=10)
    countries = store.get_top(p.id, "country", window=window, limit=10)
    devices = store.get_top(p.id, "device_type", window=window, limit=10)
    deploys = store.recent_deployments(project_id=p.id, limit=10)

    def _tag_refs(rows):
        out = []
        for r in rows:
            bot, reason = is_bot(r.key)
            out.append(
                {
                    "hostname": r.key,
                    "views": r.total,
                    "is_bot": bot,
                    "bot_reason": reason,
                }
            )
        return out

    return {
        "name": p.name,
        "domain": p.primary_domain,
        "framework": p.framework,
        "has_web_analytics": p.has_web_analytics,
        "has_speed_insights": p.has_speed_insights,
        "views_30d": store.total_views(p.id, window=window),
        "top_pages": [{"path": r.key, "views": r.total} for r in paths],
        "referrers": _tag_refs(refs),
        "countries": [{"country": r.key, "views": r.total} for r in countries],
        "devices": [{"device": r.key, "views": r.total} for r in devices],
        "recent_deploys": [
            {
                "id": d.id,
                "url": d.url,
                "state": d.state,
                "created_at_ms": d.created_at,
                "commit_message": d.commit_message,
                "commit_sha": d.commit_sha,
                "is_production": d.is_production,
            }
            for d in deploys
        ],
    }


def dark_data(store: Store) -> dict[str, Any]:
    rows = []
    for p in store.list_projects():
        views = store.total_views(p.id, "30d")
        if p.has_web_analytics and views > 0:
            continue
        rows.append(
            {
                "name": p.name,
                "domain": p.primary_domain,
                "has_web_analytics": p.has_web_analytics,
                "views_30d": views,
                "reason": (
                    "analytics disabled"
                    if not p.has_web_analytics
                    else "no traffic in 30d"
                ),
            }
        )
    return {"count": len(rows), "projects": rows}


def deploys_data(
    store: Store,
    since_ms: int | None = None,
    state: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    deploys = store.recent_deployments(limit=limit * 4, since=since_ms)
    if state:
        deploys = [d for d in deploys if d.state.upper() == state.upper()]
    projects = {p.id: p for p in store.list_projects()}
    return {
        "count": len(deploys[:limit]),
        "deploys": [
            {
                "id": d.id,
                "project": projects[d.project_id].name if d.project_id in projects else d.project_id,
                "url": d.url,
                "state": d.state,
                "is_production": d.is_production,
                "created_at_ms": d.created_at,
                "commit_message": d.commit_message,
                "commit_sha": d.commit_sha,
            }
            for d in deploys[:limit]
        ],
    }


def refs_data(
    store: Store,
    project: str | None = None,
    include_bots: bool = False,
    window: str = "30d",
) -> dict[str, Any]:
    if project:
        p = store.get_project_by_name(project)
        if not p:
            return {"error": f"No project matching '{project}'"}
        targets = [p]
    else:
        targets = store.list_projects()
    out = []
    for p in targets:
        for r in store.get_top(p.id, "referrer_hostname", window=window, limit=10):
            bot, reason = is_bot(r.key)
            if bot and not include_bots:
                continue
            out.append(
                {
                    "project": p.name,
                    "hostname": r.key,
                    "views": r.total,
                    "is_bot": bot,
                    "bot_reason": reason,
                }
            )
    return {"count": len(out), "referrers": out}


def last_sync_data(store: Store) -> dict[str, Any]:
    import time
    last = store.last_sync()
    if not last:
        return {"synced": False, "message": "never synced"}
    age_s = int(time.time() - last["started_at"] / 1000)
    return {
        "synced": True,
        "synced_at_ms": last["started_at"],
        "age_seconds": age_s,
        "stale": age_s > 1800,
        "duration_ms": last["duration_ms"],
        "projects_synced": last["projects_synced"],
        "api_calls": last["api_calls"],
        "errors": last["errors"],
    }


def trigger_sync() -> dict[str, Any]:
    token = load_token()
    team = load_team_id()
    with Store() as store, VercelClient(token, team) as client:
        result = run_sync(client, store)
    return {
        "projects_synced": result.projects_synced,
        "duration_ms": result.duration_ms,
        "api_calls": result.api_calls,
        "errors": result.errors,
    }


def denylist_data() -> dict[str, Any]:
    return {
        "count": len(BOT_REFERRERS),
        "entries": [
            {"hostname": h, "reason": r} for h, r in BOT_REFERRERS.items()
        ],
    }


def _import_mcp():
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import TextContent, Tool
    except ImportError as exc:
        raise MCPNotInstalledError(
            "MCP server requires the mcp SDK. Install with: pip install vercel-fleet[mcp]"
        ) from exc
    return Server, stdio_server, TextContent, Tool


TOOL_SPECS = [
    {
        "name": "overview",
        "description": "Cross-project Vercel analytics rollup: project list with views, real-referrer views, top referrers, deploys. Use this first to see fleet shape.",
        "schema": {
            "type": "object",
            "properties": {
                "window": {
                    "type": "string",
                    "description": "Time window key, e.g. '30d'",
                    "default": "30d",
                },
            },
        },
    },
    {
        "name": "project",
        "description": "Drill into one project — top pages, referrers (tagged bot/real), countries, devices, recent deploys.",
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name or domain"},
                "window": {"type": "string", "default": "30d"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "dark",
        "description": "List projects with analytics disabled OR zero views in 30d.",
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "deploys",
        "description": "Fleet-wide deploys. Filter by since (relative like '7d') and state (READY/ERROR/BUILDING/CANCELED).",
        "schema": {
            "type": "object",
            "properties": {
                "since": {"type": "string", "description": "Relative time like '7d' or '4h'"},
                "state": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "refs",
        "description": "Referrer hostnames across the fleet or for one project. Real-only by default.",
        "schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "include_bots": {"type": "boolean", "default": False},
                "window": {"type": "string", "default": "30d"},
            },
        },
    },
    {
        "name": "last_sync",
        "description": "When was the last sync, how old is the data, was it clean.",
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "sync",
        "description": "Pull fresh data from Vercel API (slower, ~30s for 23 projects). Prefer last_sync if just checking freshness.",
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "denylist",
        "description": "Current bot referrer denylist and reasons.",
        "schema": {"type": "object", "properties": {}},
    },
]


def _parse_since(value: str | None) -> int | None:
    if not value:
        return None
    import time
    v = value.strip().lower()
    mult = {"d": 86400, "h": 3600, "m": 60}
    if v and v[-1] in mult:
        return int((time.time() - int(v[:-1]) * mult[v[-1]]) * 1000)
    raise ValueError(f"Unsupported since: {value}")


def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    args = args or {}
    if name == "overview":
        with Store() as s:
            return overview_data(s, window=args.get("window", "30d"))
    if name == "project":
        with Store() as s:
            return project_data(s, args["name"], window=args.get("window", "30d"))
    if name == "dark":
        with Store() as s:
            return dark_data(s)
    if name == "deploys":
        with Store() as s:
            return deploys_data(
                s,
                since_ms=_parse_since(args.get("since")),
                state=args.get("state"),
                limit=args.get("limit", 50),
            )
    if name == "refs":
        with Store() as s:
            return refs_data(
                s,
                project=args.get("project"),
                include_bots=bool(args.get("include_bots", False)),
                window=args.get("window", "30d"),
            )
    if name == "last_sync":
        with Store() as s:
            return last_sync_data(s)
    if name == "sync":
        return trigger_sync()
    if name == "denylist":
        return denylist_data()
    return {"error": f"Unknown tool: {name}"}


def create_server():
    Server, _stdio_server, TextContent, Tool = _import_mcp()
    server = Server("vercel-fleet")

    @server.list_tools()
    async def _list_tools():
        return [
            Tool(name=spec["name"], description=spec["description"], inputSchema=spec["schema"])
            for spec in TOOL_SPECS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]):
        try:
            result = dispatch(name, arguments)
        except Exception as exc:
            result = {"error": str(exc), "tool": name}
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    return server


async def run_server() -> None:
    _Server, stdio_server, _TextContent, _Tool = _import_mcp()
    server = create_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
