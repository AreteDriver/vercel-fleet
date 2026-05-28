from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from vercel_fleet.cli import app
from vercel_fleet.store import DeployRow, ProjectRow, Store, TopRow, now_ms


@pytest.fixture(autouse=True)
def _wide_console(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "200")


@pytest.fixture
def populated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "fleet.db"
    monkeypatch.setattr(
        "vercel_fleet.store.default_db_path", lambda: db
    )
    s = Store(db)
    s.upsert_project(
        ProjectRow(
            id="p1", name="benchgoblins", primary_domain="benchgoblins.com",
            framework="nextjs", has_web_analytics=True, has_speed_insights=True,
            updated_at=now_ms(),
        )
    )
    s.upsert_project(
        ProjectRow(
            id="p2", name="aretedriver", primary_domain="aretedriver.dev",
            framework="static", has_web_analytics=True, has_speed_insights=False,
            updated_at=now_ms(),
        )
    )
    s.upsert_project(
        ProjectRow(
            id="p3", name="darkproject", primary_domain=None, framework=None,
            has_web_analytics=False, has_speed_insights=False, updated_at=now_ms(),
        )
    )
    s.replace_traffic_top("p1", "path", "30d", [
        TopRow("p1", "path", "30d", "/", 100, 80, now_ms()),
        TopRow("p1", "path", "30d", "/draft", 76, 50, now_ms()),
    ])
    s.replace_traffic_top("p1", "referrer_hostname", "30d", [
        TopRow("p1", "referrer_hostname", "30d", "google.com", 120, 90, now_ms()),
        TopRow("p1", "referrer_hostname", "30d", "vercel.com", 50, 30, now_ms()),
    ])
    s.replace_traffic_top("p1", "country", "30d", [
        TopRow("p1", "country", "30d", "US", 150, 100, now_ms()),
    ])
    s.replace_traffic_top("p2", "path", "30d", [
        TopRow("p2", "path", "30d", "/", 22, 22, now_ms()),
    ])
    s.replace_traffic_top("p2", "referrer_hostname", "30d", [
        TopRow("p2", "referrer_hostname", "30d", "apexoo.com", 20, 15, now_ms()),
    ])
    s.upsert_deployment(DeployRow(
        id="d1", project_id="p1", url="x.vercel.app", state="READY",
        ready_state="READY", created_at=now_ms() - 3600000,
        commit_message="ship: BG fix", commit_sha="abc",
        is_production=True,
    ))
    s.write_sync_log(now_ms(), 1500, 3, 12, [])
    s.close()
    return db


def test_overview_command_renders(populated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["overview"])
    assert result.exit_code == 0
    assert "benchgoblins" in result.stdout
    # Hidden dark project shouldn't be in overview list
    assert "darkproject" not in result.stdout


def test_dark_command_lists_dark(populated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["dark"])
    assert result.exit_code == 0
    assert "darkproject" in result.stdout


def test_deploys_command(populated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["deploys"])
    assert result.exit_code == 0
    assert "ship: BG fix" in result.stdout


def test_project_command(populated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["project", "benchgoblins"])
    assert result.exit_code == 0
    assert "benchgoblins" in result.stdout
    assert "google.com" in result.stdout


def test_project_command_not_found(populated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["project", "nope"])
    assert result.exit_code == 1


def test_refs_command_filters_bots(populated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["refs"])
    assert result.exit_code == 0
    assert "google.com" in result.stdout
    assert "apexoo.com" not in result.stdout


def test_refs_include_bots(populated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["refs", "--include-bots"])
    assert result.exit_code == 0
    assert "apexoo.com" in result.stdout


def test_denylist_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["denylist"])
    assert result.exit_code == 0
    assert "apexoo.com" in result.stdout


def test_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "vercel-fleet" in result.stdout
