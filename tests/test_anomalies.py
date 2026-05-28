from __future__ import annotations

import time

from vercel_fleet.anomalies import detect
from vercel_fleet.store import DeployRow, ProjectRow, Store, TopRow, now_ms


def _seed_project(store: Store, id_: str, name: str, wa: bool) -> None:
    store.upsert_project(
        ProjectRow(
            id=id_, name=name, primary_domain=f"{name}.dev", framework="nextjs",
            has_web_analytics=wa, has_speed_insights=False, updated_at=now_ms(),
        )
    )


def test_detect_failed_deploys(tmp_store: Store) -> None:
    _seed_project(tmp_store, "p1", "alpha", True)
    tmp_store.upsert_deployment(
        DeployRow(
            id="d1", project_id="p1", url="x", state="ERROR", ready_state="ERROR",
            created_at=int(time.time() * 1000), commit_message="bad", commit_sha="",
            is_production=False,
        )
    )
    out = detect(tmp_store, window_days=7)
    kinds = {a.kind for a in out}
    assert "failed_deploy" in kinds


def test_detect_dark_no_analytics(tmp_store: Store) -> None:
    _seed_project(tmp_store, "p2", "darko", False)
    out = detect(tmp_store)
    assert any(a.kind == "dark_project" and a.project == "darko" for a in out)


def test_detect_dark_no_traffic(tmp_store: Store) -> None:
    _seed_project(tmp_store, "p3", "empty", True)
    out = detect(tmp_store)
    assert any(a.kind == "dark_project" and a.project == "empty" for a in out)


def test_detect_quality_referrer(tmp_store: Store) -> None:
    _seed_project(tmp_store, "p4", "trafficky", True)
    tmp_store.replace_traffic_top(
        "p4", "referrer_hostname", "30d",
        [TopRow("p4", "referrer_hostname", "30d", "github.com", 100, 80, now_ms())],
    )
    # Add path views so it's not dark
    tmp_store.replace_traffic_top(
        "p4", "path", "30d",
        [TopRow("p4", "path", "30d", "/", 100, 80, now_ms())],
    )
    out = detect(tmp_store)
    assert any(a.kind == "quality_ref" and "github.com" in a.detail for a in out)


def test_quality_referrer_ignores_bots(tmp_store: Store) -> None:
    _seed_project(tmp_store, "p5", "botty", True)
    tmp_store.replace_traffic_top(
        "p5", "referrer_hostname", "30d",
        [TopRow("p5", "referrer_hostname", "30d", "apexoo.com", 500, 400, now_ms())],
    )
    tmp_store.replace_traffic_top(
        "p5", "path", "30d",
        [TopRow("p5", "path", "30d", "/", 500, 400, now_ms())],
    )
    out = detect(tmp_store)
    assert not any(a.kind == "quality_ref" and a.project == "botty" for a in out)
