from __future__ import annotations

from vercel_fleet.store import DeployRow, ProjectRow, Store, TopRow, now_ms


def make_project(id_: str = "prj_a", name: str = "a", views_enabled: bool = True) -> ProjectRow:
    return ProjectRow(
        id=id_, name=name, primary_domain=f"{name}.dev",
        framework="nextjs", has_web_analytics=views_enabled,
        has_speed_insights=False, updated_at=now_ms(),
    )


def test_upsert_project_idempotent(tmp_store: Store) -> None:
    p = make_project()
    tmp_store.upsert_project(p)
    tmp_store.upsert_project(p)
    rows = tmp_store.list_projects()
    assert len(rows) == 1


def test_upsert_project_updates_fields(tmp_store: Store) -> None:
    tmp_store.upsert_project(make_project(name="orig"))
    tmp_store.upsert_project(make_project(name="renamed"))
    rows = tmp_store.list_projects()
    assert rows[0].name == "renamed"


def test_get_project_by_name(tmp_store: Store) -> None:
    tmp_store.upsert_project(make_project(name="hello"))
    p = tmp_store.get_project_by_name("hello")
    assert p is not None
    assert p.name == "hello"
    assert tmp_store.get_project_by_name("nope") is None


def test_get_project_by_domain(tmp_store: Store) -> None:
    tmp_store.upsert_project(make_project(name="bench"))
    p = tmp_store.get_project_by_name("bench.dev")
    assert p is not None
    assert p.name == "bench"


def test_replace_traffic_top_idempotent(tmp_store: Store) -> None:
    pid = "prj_t"
    tmp_store.upsert_project(make_project(id_=pid, name="t"))
    rows1 = [
        TopRow(pid, "path", "30d", "/", 100, 50, now_ms()),
        TopRow(pid, "path", "30d", "/about", 30, 20, now_ms()),
    ]
    tmp_store.replace_traffic_top(pid, "path", "30d", rows1)
    rows2 = [TopRow(pid, "path", "30d", "/new", 5, 5, now_ms())]
    tmp_store.replace_traffic_top(pid, "path", "30d", rows2)
    stored = tmp_store.get_top(pid, "path", "30d", limit=10)
    assert len(stored) == 1
    assert stored[0].key == "/new"


def test_total_views(tmp_store: Store) -> None:
    pid = "prj_t"
    tmp_store.upsert_project(make_project(id_=pid, name="t"))
    rows = [
        TopRow(pid, "path", "30d", "/", 100, 50, now_ms()),
        TopRow(pid, "path", "30d", "/about", 30, 20, now_ms()),
    ]
    tmp_store.replace_traffic_top(pid, "path", "30d", rows)
    assert tmp_store.total_views(pid, "30d") == 130
    assert tmp_store.total_views(pid, "7d") == 0


def test_upsert_deployment_and_query(tmp_store: Store) -> None:
    pid = "prj_t"
    tmp_store.upsert_project(make_project(id_=pid, name="t"))
    d = DeployRow(
        id="dpl_1", project_id=pid, url="x.vercel.app", state="READY",
        ready_state="READY", created_at=now_ms(),
        commit_message="initial", commit_sha="abc", is_production=True,
    )
    tmp_store.upsert_deployment(d)
    rows = tmp_store.recent_deployments(project_id=pid)
    assert len(rows) == 1
    assert rows[0].commit_message == "initial"


def test_recent_deployments_since(tmp_store: Store) -> None:
    pid = "prj_t"
    tmp_store.upsert_project(make_project(id_=pid, name="t"))
    now = now_ms()
    old = DeployRow(
        id="d_old", project_id=pid, url="o", state="READY", ready_state="READY",
        created_at=now - 86400000 * 10, commit_message="old", commit_sha="o",
        is_production=False,
    )
    new = DeployRow(
        id="d_new", project_id=pid, url="n", state="READY", ready_state="READY",
        created_at=now - 3600000, commit_message="new", commit_sha="n",
        is_production=True,
    )
    tmp_store.upsert_deployment(old)
    tmp_store.upsert_deployment(new)
    recent = tmp_store.recent_deployments(since=now - 86400000)
    assert len(recent) == 1
    assert recent[0].id == "d_new"


def test_sync_log_roundtrip(tmp_store: Store) -> None:
    tmp_store.write_sync_log(
        started_at=now_ms(), duration_ms=5000, projects_synced=3,
        api_calls=15, errors=["a", "b"],
    )
    last = tmp_store.last_sync()
    assert last is not None
    assert last["projects_synced"] == 3
    assert last["errors"] == ["a", "b"]


def test_sync_log_none_when_empty(tmp_store: Store) -> None:
    assert tmp_store.last_sync() is None
