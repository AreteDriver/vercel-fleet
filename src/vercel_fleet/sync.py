from __future__ import annotations

import time
from dataclasses import dataclass

from vercel_fleet.client import ANALYTICS_DIMENSIONS, VercelAPIError, VercelClient
from vercel_fleet.store import DeployRow, ProjectRow, Store, TopRow, now_ms


@dataclass
class SyncResult:
    projects_synced: int
    api_calls: int
    duration_ms: int
    errors: list[str]


def run_sync(
    client: VercelClient,
    store: Store,
    *,
    window_days: int = 30,
    deploy_limit: int = 10,
    on_progress=None,
) -> SyncResult:
    started = time.time()
    api_calls = 0
    errors: list[str] = []

    try:
        projects = client.list_projects()
        api_calls += 1
    except VercelAPIError as exc:
        errors.append(f"list_projects: {exc}")
        return SyncResult(
            projects_synced=0,
            api_calls=api_calls,
            duration_ms=int((time.time() - started) * 1000),
            errors=errors,
        )

    window_key = f"{window_days}d"
    fetched_at = now_ms()

    for project in projects:
        store.upsert_project(
            ProjectRow(
                id=project.id,
                name=project.name,
                primary_domain=project.primary_domain,
                framework=project.framework,
                has_web_analytics=project.has_web_analytics,
                has_speed_insights=project.has_speed_insights,
                updated_at=fetched_at,
            )
        )
        if on_progress:
            on_progress(project.name)

        # Pull analytics dimensions only for projects with analytics data
        if project.has_web_analytics:
            for dim in ANALYTICS_DIMENSIONS:
                try:
                    rows = client.analytics_top(
                        project.id, dim, days=window_days, limit=10
                    )
                    api_calls += 1
                except VercelAPIError as exc:
                    errors.append(f"{project.name}/{dim}: {exc}")
                    continue
                store.replace_traffic_top(
                    project.id,
                    dim,
                    window_key,
                    [
                        TopRow(
                            project_id=project.id,
                            dimension=dim,
                            window=window_key,
                            key=r.key,
                            total=r.total,
                            devices=r.devices,
                            fetched_at=fetched_at,
                        )
                        for r in rows
                    ],
                )

        # Recent deployments — always
        try:
            deployments = client.list_deployments(project.id, limit=deploy_limit)
            api_calls += 1
        except VercelAPIError as exc:
            errors.append(f"{project.name}/deploys: {exc}")
            continue
        for d in deployments:
            store.upsert_deployment(
                DeployRow(
                    id=d.id,
                    project_id=d.project_id,
                    url=d.url,
                    state=d.state,
                    ready_state=d.ready_state,
                    created_at=d.created_at,
                    commit_message=d.commit_message,
                    commit_sha=d.commit_sha,
                    is_production=d.is_production,
                )
            )

    duration_ms = int((time.time() - started) * 1000)
    started_at_ms = int(started * 1000)
    store.write_sync_log(
        started_at=started_at_ms,
        duration_ms=duration_ms,
        projects_synced=len(projects),
        api_calls=api_calls,
        errors=errors,
    )
    return SyncResult(
        projects_synced=len(projects),
        api_calls=api_calls,
        duration_ms=duration_ms,
        errors=errors,
    )
