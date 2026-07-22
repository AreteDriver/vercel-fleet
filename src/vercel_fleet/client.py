from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

import httpx

API_BASE = "https://api.vercel.com"
ANALYTICS_DIMENSIONS = ("path", "referrer_hostname", "country", "device_type")


class VercelAPIError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Vercel API {status}: {message}")
        self.status = status
        self.message = message


@dataclass
class Project:
    id: str
    name: str
    primary_domain: str | None
    framework: str | None
    has_web_analytics: bool
    has_speed_insights: bool

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Project:
        wa = raw.get("webAnalytics") or {}
        si = raw.get("speedInsights") or {}
        domain = None
        targets = raw.get("targets") or {}
        prod = targets.get("production") or {}
        alias = prod.get("alias") or []
        if alias:
            domain = alias[0]
        return cls(
            id=raw["id"],
            name=raw["name"],
            primary_domain=domain,
            framework=raw.get("framework"),
            has_web_analytics=bool(wa.get("hasData")),
            has_speed_insights=bool(si.get("hasData")),
        )


@dataclass
class Deployment:
    id: str
    project_id: str
    url: str
    state: str
    ready_state: str
    created_at: int
    commit_message: str
    commit_sha: str
    is_production: bool

    @classmethod
    def from_api(cls, raw: dict[str, Any], project_id: str) -> Deployment:
        meta = raw.get("meta") or {}
        return cls(
            id=raw["uid"],
            project_id=project_id,
            url=raw.get("url", ""),
            state=raw.get("state", ""),
            ready_state=raw.get("readyState", ""),
            created_at=int(raw.get("created", 0)),
            commit_message=(meta.get("githubCommitMessage") or "")[:240],
            commit_sha=meta.get("githubCommitSha", ""),
            is_production=bool(raw.get("target") == "production"),
        )


@dataclass
class TopValue:
    key: str
    total: int
    devices: int


def _iso(dt_obj: dt.datetime) -> str:
    return dt_obj.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class VercelClient:
    def __init__(self, token: str, team_id: str, timeout: float = 30.0) -> None:
        self.token = token
        self.team_id = team_id
        self._client = httpx.Client(
            base_url=API_BASE,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> VercelClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        merged: dict[str, Any] = {**(params or {})}
        if self.team_id:
            merged["teamId"] = self.team_id
        resp = self._client.get(path, params=merged)
        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", {})
                msg = err.get("message", resp.text[:200])
            except Exception:
                msg = resp.text[:200]
            raise VercelAPIError(resp.status_code, msg)
        return resp.json()

    def list_projects(self, limit: int = 100) -> list[Project]:
        out: list[Project] = []
        until: str | None = None
        while True:
            params: dict[str, Any] = {"limit": limit}
            if until:
                params["until"] = until
            data = self._get("/v9/projects", params=params)
            for raw in data.get("projects", []):
                out.append(Project.from_api(raw))
            pagination = data.get("pagination") or {}
            until = pagination.get("next")
            if not until:
                break
        return out

    def list_deployments(
        self,
        project_id: str,
        limit: int = 10,
        since: int | None = None,
    ) -> list[Deployment]:
        params: dict[str, Any] = {"projectId": project_id, "limit": limit}
        if since is not None:
            params["since"] = since
        data = self._get("/v6/deployments", params=params)
        return [Deployment.from_api(d, project_id) for d in data.get("deployments", [])]

    def analytics_top(
        self,
        project_id: str,
        dimension: str,
        days: int = 30,
        limit: int = 10,
    ) -> list[TopValue]:
        if dimension not in ANALYTICS_DIMENSIONS:
            raise ValueError(f"Unsupported dimension: {dimension}")
        now = dt.datetime.now(dt.timezone.utc)
        params = {
            "projectId": project_id,
            "from": _iso(now - dt.timedelta(days=days)),
            "to": _iso(now),
            "type": dimension,
            "limit": limit,
        }
        try:
            data = self._get("/web-analytics/stats", params=params)
        except VercelAPIError as exc:
            # Project may not have analytics enabled — treat as empty
            if exc.status in (400, 403, 404):
                return []
            raise
        return [
            TopValue(
                key=str(item.get("key", "")),
                total=int(item.get("total", 0)),
                devices=int(item.get("devices", 0)),
            )
            for item in data.get("data", [])
        ]
