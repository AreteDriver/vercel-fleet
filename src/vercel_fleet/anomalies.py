from __future__ import annotations

import time
from dataclasses import dataclass

from vercel_fleet.denylist import is_bot
from vercel_fleet.store import Store


@dataclass
class Anomaly:
    kind: str
    project: str
    detail: str


def detect(store: Store, window_days: int = 7) -> list[Anomaly]:
    out: list[Anomaly] = []
    cutoff = int((time.time() - window_days * 86400) * 1000)

    projects = store.list_projects()

    # Failed deploys in window
    for p in projects:
        deploys = store.recent_deployments(project_id=p.id, since=cutoff, limit=50)
        errors = [d for d in deploys if d.state == "ERROR"]
        if errors:
            out.append(
                Anomaly(
                    kind="failed_deploy",
                    project=p.name,
                    detail=f"{len(errors)} failed deploy(s) in last {window_days}d",
                )
            )

    # Dark projects (no analytics OR 0 views in 30d)
    for p in projects:
        views = store.total_views(p.id, window="30d")
        if not p.has_web_analytics or views == 0:
            out.append(
                Anomaly(
                    kind="dark_project",
                    project=p.name,
                    detail="analytics disabled" if not p.has_web_analytics
                    else "0 views in 30d",
                )
            )

    # New high-quality refs (single real referrer with > 50 views)
    for p in projects:
        refs = store.get_top(p.id, "referrer_hostname", window="30d", limit=5)
        for r in refs:
            bot, _ = is_bot(r.key)
            if not bot and r.total >= 50:
                out.append(
                    Anomaly(
                        kind="quality_ref",
                        project=p.name,
                        detail=f"{r.key} → {r.total} views",
                    )
                )

    return out
