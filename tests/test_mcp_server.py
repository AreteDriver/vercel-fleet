from __future__ import annotations

from pathlib import Path

import pytest

from vercel_fleet.mcp_server import (
    TOOL_SPECS,
    _parse_since,
    dark_data,
    denylist_data,
    deploys_data,
    dispatch,
    last_sync_data,
    overview_data,
    project_data,
    refs_data,
)
from vercel_fleet.store import DeployRow, ProjectRow, Store, TopRow, now_ms


@pytest.fixture
def store_with_data(tmp_path: Path) -> Store:
    s = Store(tmp_path / "fleet.db")
    s.upsert_project(
        ProjectRow(
            id="p1", name="bench", primary_domain="bench.com",
            framework="nextjs", has_web_analytics=True, has_speed_insights=True,
            updated_at=now_ms(),
        )
    )
    s.upsert_project(
        ProjectRow(
            id="p2", name="darko", primary_domain=None, framework=None,
            has_web_analytics=False, has_speed_insights=False, updated_at=now_ms(),
        )
    )
    s.replace_traffic_top("p1", "path", "30d", [
        TopRow("p1", "path", "30d", "/", 100, 80, now_ms()),
        TopRow("p1", "path", "30d", "/x", 30, 20, now_ms()),
    ])
    s.replace_traffic_top("p1", "referrer_hostname", "30d", [
        TopRow("p1", "referrer_hostname", "30d", "google.com", 90, 70, now_ms()),
        TopRow("p1", "referrer_hostname", "30d", "apexoo.com", 40, 30, now_ms()),
    ])
    s.replace_traffic_top("p1", "country", "30d", [
        TopRow("p1", "country", "30d", "US", 130, 100, now_ms()),
    ])
    s.replace_traffic_top("p1", "device_type", "30d", [
        TopRow("p1", "device_type", "30d", "desktop", 100, 80, now_ms()),
    ])
    s.upsert_deployment(DeployRow(
        id="d1", project_id="p1", url="x.vercel.app", state="READY",
        ready_state="READY", created_at=now_ms() - 3600000,
        commit_message="ship", commit_sha="abc", is_production=True,
    ))
    s.upsert_deployment(DeployRow(
        id="d2", project_id="p1", url="y.vercel.app", state="ERROR",
        ready_state="ERROR", created_at=now_ms() - 7200000,
        commit_message="broke", commit_sha="def", is_production=False,
    ))
    s.write_sync_log(now_ms(), 5000, 2, 10, [])
    return s


def test_overview_shape(store_with_data: Store) -> None:
    out = overview_data(store_with_data)
    assert "totals" in out
    assert out["totals"]["projects"] == 2
    assert out["totals"]["live"] == 1
    assert out["totals"]["dark"] == 1
    assert out["totals"]["views"] == 130
    # bench has google.com (90) as real ref; apexoo (40) is bot
    assert out["totals"]["real_referrer_views"] == 90
    assert any(p["name"] == "bench" for p in out["projects"])
    assert all(not p["is_dark"] for p in out["projects"])


def test_overview_includes_anomalies(store_with_data: Store) -> None:
    out = overview_data(store_with_data)
    assert isinstance(out["anomalies"], list)
    kinds = {a["kind"] for a in out["anomalies"]}
    assert "failed_deploy" in kinds
    assert "dark_project" in kinds


def test_project_shape(store_with_data: Store) -> None:
    out = project_data(store_with_data, "bench")
    assert out["name"] == "bench"
    assert out["views_30d"] == 130
    assert len(out["top_pages"]) == 2
    assert any(r["is_bot"] for r in out["referrers"])
    assert any(not r["is_bot"] for r in out["referrers"])
    assert len(out["recent_deploys"]) == 2


def test_project_not_found(store_with_data: Store) -> None:
    out = project_data(store_with_data, "nope")
    assert "error" in out


def test_dark_shape(store_with_data: Store) -> None:
    out = dark_data(store_with_data)
    assert out["count"] == 1
    assert out["projects"][0]["name"] == "darko"


def test_deploys_filter_state(store_with_data: Store) -> None:
    out = deploys_data(store_with_data, state="ERROR")
    assert out["count"] == 1
    assert out["deploys"][0]["state"] == "ERROR"


def test_deploys_no_filter(store_with_data: Store) -> None:
    out = deploys_data(store_with_data)
    assert out["count"] == 2


def test_refs_filters_bots(store_with_data: Store) -> None:
    out = refs_data(store_with_data)
    hostnames = {r["hostname"] for r in out["referrers"]}
    assert "google.com" in hostnames
    assert "apexoo.com" not in hostnames


def test_refs_include_bots(store_with_data: Store) -> None:
    out = refs_data(store_with_data, include_bots=True)
    hostnames = {r["hostname"] for r in out["referrers"]}
    assert "apexoo.com" in hostnames


def test_refs_specific_project(store_with_data: Store) -> None:
    out = refs_data(store_with_data, project="bench")
    assert all(r["project"] == "bench" for r in out["referrers"])


def test_refs_missing_project(store_with_data: Store) -> None:
    out = refs_data(store_with_data, project="nope")
    assert "error" in out


def test_last_sync_data(store_with_data: Store) -> None:
    out = last_sync_data(store_with_data)
    assert out["synced"] is True
    assert out["projects_synced"] == 2
    assert "age_seconds" in out


def test_last_sync_never(tmp_path: Path) -> None:
    s = Store(tmp_path / "x.db")
    out = last_sync_data(s)
    assert out["synced"] is False
    s.close()


def test_denylist_data() -> None:
    out = denylist_data()
    assert out["count"] >= 8
    assert any(e["hostname"] == "apexoo.com" for e in out["entries"])


def test_parse_since() -> None:
    assert _parse_since(None) is None
    assert _parse_since("7d") is not None
    assert _parse_since("4h") is not None
    assert _parse_since("30m") is not None


def test_parse_since_invalid() -> None:
    with pytest.raises(ValueError):
        _parse_since("xyz")


def test_tool_specs_complete() -> None:
    # Every dispatch path has a TOOL_SPECS entry
    spec_names = {s["name"] for s in TOOL_SPECS}
    for needed in ["overview", "project", "dark", "deploys", "refs",
                   "last_sync", "sync", "denylist"]:
        assert needed in spec_names


def test_tool_specs_schema_valid() -> None:
    for spec in TOOL_SPECS:
        assert "name" in spec
        assert "description" in spec
        assert "schema" in spec
        assert spec["schema"]["type"] == "object"
        assert "properties" in spec["schema"]


def test_dispatch_unknown_returns_error() -> None:
    out = dispatch("not_a_real_tool", {})
    assert "error" in out


def test_dispatch_denylist_routes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "vercel_fleet.mcp_server.Store",
        lambda: Store(tmp_path / "x.db"),
    )
    out = dispatch("denylist", {})
    assert out["count"] >= 8
