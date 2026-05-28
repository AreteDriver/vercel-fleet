from __future__ import annotations

import httpx
import pytest

from vercel_fleet.client import (
    Deployment,
    Project,
    VercelAPIError,
    VercelClient,
)


def test_project_from_api(project_raw: dict) -> None:
    p = Project.from_api(project_raw)
    assert p.id == "prj_test1"
    assert p.name == "test-project"
    assert p.has_web_analytics is True
    assert p.has_speed_insights is False
    assert p.primary_domain == "test-project.aretedriver.dev"


def test_project_from_api_no_analytics() -> None:
    raw = {"id": "prj_x", "name": "no-wa", "webAnalytics": None, "speedInsights": None}
    p = Project.from_api(raw)
    assert p.has_web_analytics is False
    assert p.primary_domain is None


def test_deployment_from_api(deploy_raw: dict) -> None:
    d = Deployment.from_api(deploy_raw, project_id="prj_x")
    assert d.id == "dpl_abc"
    assert d.state == "READY"
    assert d.is_production is True
    assert d.commit_message == "feat: add thing"


def test_client_raises_on_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Unauthorized"}})

    transport = httpx.MockTransport(handler)
    c = VercelClient("tok", "team_x")
    c._client = httpx.Client(
        base_url="https://api.vercel.com",
        headers={"Authorization": "Bearer tok"},
        transport=transport,
    )
    with pytest.raises(VercelAPIError) as exc:
        c._get("/v9/projects")
    assert exc.value.status == 401


def test_list_projects_pagination() -> None:
    pages = [
        {
            "projects": [
                {"id": "p1", "name": "one"},
                {"id": "p2", "name": "two"},
            ],
            "pagination": {"next": "cursor_x"},
        },
        {
            "projects": [{"id": "p3", "name": "three"}],
            "pagination": {"next": None},
        },
    ]
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        i = call_count["n"]
        call_count["n"] += 1
        return httpx.Response(200, json=pages[i])

    transport = httpx.MockTransport(handler)
    c = VercelClient("tok", "team_x")
    c._client = httpx.Client(
        base_url="https://api.vercel.com",
        headers={"Authorization": "Bearer tok"},
        transport=transport,
    )
    projs = c.list_projects()
    assert len(projs) == 3
    assert call_count["n"] == 2


def test_analytics_top_swallows_4xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "no analytics"}})

    transport = httpx.MockTransport(handler)
    c = VercelClient("tok", "team_x")
    c._client = httpx.Client(
        base_url="https://api.vercel.com",
        headers={"Authorization": "Bearer tok"},
        transport=transport,
    )
    result = c.analytics_top("prj_x", "path")
    assert result == []


def test_analytics_top_invalid_dimension() -> None:
    c = VercelClient("tok", "team_x")
    with pytest.raises(ValueError):
        c.analytics_top("prj_x", "not_a_real_dim")
