from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platformdirs import user_data_path

SCHEMA_VERSION = 1


def default_db_path() -> Path:
    base = user_data_path("vercel-fleet", appauthor=False)
    base.mkdir(parents=True, exist_ok=True)
    return base / "fleet.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    primary_domain TEXT,
    framework TEXT,
    has_web_analytics INTEGER DEFAULT 0,
    has_speed_insights INTEGER DEFAULT 0,
    updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS traffic_top (
    project_id TEXT,
    dimension TEXT,
    window TEXT,
    key TEXT,
    total INTEGER,
    devices INTEGER,
    fetched_at INTEGER,
    PRIMARY KEY (project_id, dimension, window, key)
);

CREATE TABLE IF NOT EXISTS deployments (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    url TEXT,
    state TEXT,
    ready_state TEXT,
    created_at INTEGER,
    commit_message TEXT,
    commit_sha TEXT,
    is_production INTEGER
);

CREATE INDEX IF NOT EXISTS deployments_project_idx ON deployments(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS sync_log (
    started_at INTEGER PRIMARY KEY,
    duration_ms INTEGER,
    projects_synced INTEGER,
    api_calls INTEGER,
    errors TEXT
);
"""


@dataclass
class ProjectRow:
    id: str
    name: str
    primary_domain: str | None
    framework: str | None
    has_web_analytics: bool
    has_speed_insights: bool
    updated_at: int


@dataclass
class DeployRow:
    id: str
    project_id: str
    url: str
    state: str
    ready_state: str
    created_at: int
    commit_message: str
    commit_sha: str
    is_production: bool


@dataclass
class TopRow:
    project_id: str
    dimension: str
    window: str
    key: str
    total: int
    devices: int
    fetched_at: int


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _migrate(self) -> None:
        with self._conn:
            self._conn.executescript(SCHEMA)
            cur = self._conn.execute("PRAGMA user_version")
            current = cur.fetchone()[0]
            if current < SCHEMA_VERSION:
                self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def transaction(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def upsert_project(self, row: ProjectRow) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, primary_domain, framework,
                    has_web_analytics, has_speed_insights, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    primary_domain = excluded.primary_domain,
                    framework = excluded.framework,
                    has_web_analytics = excluded.has_web_analytics,
                    has_speed_insights = excluded.has_speed_insights,
                    updated_at = excluded.updated_at
                """,
                (
                    row.id, row.name, row.primary_domain, row.framework,
                    int(row.has_web_analytics), int(row.has_speed_insights),
                    row.updated_at,
                ),
            )

    def upsert_deployment(self, row: DeployRow) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO deployments (id, project_id, url, state, ready_state,
                    created_at, commit_message, commit_sha, is_production)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    state = excluded.state,
                    ready_state = excluded.ready_state,
                    commit_message = excluded.commit_message
                """,
                (
                    row.id, row.project_id, row.url, row.state, row.ready_state,
                    row.created_at, row.commit_message, row.commit_sha,
                    int(row.is_production),
                ),
            )

    def replace_traffic_top(
        self,
        project_id: str,
        dimension: str,
        window: str,
        rows: list[TopRow],
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM traffic_top WHERE project_id=? AND dimension=? AND window=?",
                (project_id, dimension, window),
            )
            conn.executemany(
                """
                INSERT INTO traffic_top
                    (project_id, dimension, window, key, total, devices, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (r.project_id, r.dimension, r.window, r.key, r.total,
                     r.devices, r.fetched_at)
                    for r in rows
                ],
            )

    def list_projects(self) -> list[ProjectRow]:
        cur = self._conn.execute("SELECT * FROM projects ORDER BY name")
        return [
            ProjectRow(
                id=r["id"], name=r["name"], primary_domain=r["primary_domain"],
                framework=r["framework"],
                has_web_analytics=bool(r["has_web_analytics"]),
                has_speed_insights=bool(r["has_speed_insights"]),
                updated_at=r["updated_at"] or 0,
            )
            for r in cur.fetchall()
        ]

    def get_project_by_name(self, name: str) -> ProjectRow | None:
        cur = self._conn.execute(
            "SELECT * FROM projects WHERE name=? OR primary_domain=? LIMIT 1",
            (name, name),
        )
        r = cur.fetchone()
        if not r:
            return None
        return ProjectRow(
            id=r["id"], name=r["name"], primary_domain=r["primary_domain"],
            framework=r["framework"],
            has_web_analytics=bool(r["has_web_analytics"]),
            has_speed_insights=bool(r["has_speed_insights"]),
            updated_at=r["updated_at"] or 0,
        )

    def get_top(
        self, project_id: str, dimension: str, window: str = "30d", limit: int = 10
    ) -> list[TopRow]:
        cur = self._conn.execute(
            """
            SELECT * FROM traffic_top
            WHERE project_id=? AND dimension=? AND window=?
            ORDER BY total DESC LIMIT ?
            """,
            (project_id, dimension, window, limit),
        )
        return [
            TopRow(
                project_id=r["project_id"], dimension=r["dimension"],
                window=r["window"], key=r["key"], total=r["total"],
                devices=r["devices"], fetched_at=r["fetched_at"],
            )
            for r in cur.fetchall()
        ]

    def total_views(self, project_id: str, window: str = "30d") -> int:
        cur = self._conn.execute(
            """
            SELECT COALESCE(SUM(total), 0) AS total FROM traffic_top
            WHERE project_id=? AND dimension='path' AND window=?
            """,
            (project_id, window),
        )
        return int(cur.fetchone()["total"])

    def recent_deployments(
        self, project_id: str | None = None, limit: int = 50, since: int | None = None,
    ) -> list[DeployRow]:
        q = "SELECT * FROM deployments WHERE 1=1"
        args: list[Any] = []
        if project_id:
            q += " AND project_id=?"
            args.append(project_id)
        if since is not None:
            q += " AND created_at >= ?"
            args.append(since)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        cur = self._conn.execute(q, args)
        return [
            DeployRow(
                id=r["id"], project_id=r["project_id"], url=r["url"],
                state=r["state"], ready_state=r["ready_state"],
                created_at=r["created_at"],
                commit_message=r["commit_message"] or "",
                commit_sha=r["commit_sha"] or "",
                is_production=bool(r["is_production"]),
            )
            for r in cur.fetchall()
        ]

    def write_sync_log(
        self, started_at: int, duration_ms: int, projects_synced: int,
        api_calls: int, errors: list[str],
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO sync_log
                    (started_at, duration_ms, projects_synced, api_calls, errors)
                VALUES (?, ?, ?, ?, ?)
                """,
                (started_at, duration_ms, projects_synced, api_calls, json.dumps(errors)),
            )

    def last_sync(self) -> dict[str, Any] | None:
        cur = self._conn.execute(
            "SELECT * FROM sync_log ORDER BY started_at DESC LIMIT 1"
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "started_at": r["started_at"],
            "duration_ms": r["duration_ms"],
            "projects_synced": r["projects_synced"],
            "api_calls": r["api_calls"],
            "errors": json.loads(r["errors"] or "[]"),
        }


def now_ms() -> int:
    return int(time.time() * 1000)
