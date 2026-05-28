from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vercel_fleet.client import Deployment, Project, TopValue, VercelAPIError
from vercel_fleet.store import Store
from vercel_fleet.sync import run_sync


@pytest.fixture
def fake_client() -> MagicMock:
    c = MagicMock()
    c.list_projects.return_value = [
        Project(
            id="p1", name="alpha", primary_domain="alpha.dev",
            framework="nextjs", has_web_analytics=True, has_speed_insights=False,
        ),
        Project(
            id="p2", name="beta", primary_domain=None,
            framework="astro", has_web_analytics=False, has_speed_insights=False,
        ),
    ]
    c.analytics_top.return_value = [TopValue(key="/", total=10, devices=5)]
    c.list_deployments.return_value = [
        Deployment(
            id="d1", project_id="p1", url="u", state="READY", ready_state="READY",
            created_at=1779000000000, commit_message="msg", commit_sha="a",
            is_production=True,
        )
    ]
    return c


def test_sync_happy_path(fake_client: MagicMock, tmp_store: Store) -> None:
    result = run_sync(fake_client, tmp_store)
    assert result.projects_synced == 2
    assert not result.errors
    # alpha has analytics: 4 dims + 1 deploys call = 5
    # beta has no analytics: 1 deploys call
    # plus list_projects = 1
    # total = 1 + 5 + 1 = 7
    assert result.api_calls == 7
    projects = tmp_store.list_projects()
    assert len(projects) == 2


def test_sync_partial_analytics_failure(fake_client: MagicMock, tmp_store: Store) -> None:
    def raising_analytics(*_a, **_kw):
        raise VercelAPIError(500, "boom")

    fake_client.analytics_top.side_effect = raising_analytics
    result = run_sync(fake_client, tmp_store)
    assert result.errors  # captured
    assert result.projects_synced == 2  # still recorded
    # deployments still got pulled
    deploys = tmp_store.recent_deployments()
    assert len(deploys) == 1


def test_sync_writes_log(fake_client: MagicMock, tmp_store: Store) -> None:
    run_sync(fake_client, tmp_store)
    log = tmp_store.last_sync()
    assert log is not None
    assert log["projects_synced"] == 2


def test_sync_fatal_list_projects(tmp_store: Store) -> None:
    c = MagicMock()
    c.list_projects.side_effect = VercelAPIError(401, "no auth")
    result = run_sync(c, tmp_store)
    assert result.projects_synced == 0
    assert result.errors
