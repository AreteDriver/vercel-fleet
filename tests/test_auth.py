from __future__ import annotations

from pathlib import Path

import pytest

from vercel_fleet.auth import AuthError, load_team_id, load_token


def test_load_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL_TOKEN", "tok_env")
    assert load_token() == "tok_env"


def test_load_token_from_auth_file(fake_auth_json: Path) -> None:
    assert load_token() == "tok_fake_123"


def test_load_token_missing_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    monkeypatch.setattr(
        "vercel_fleet.auth.VERCEL_CLI_AUTH_PATH", tmp_path / "missing.json"
    )
    with pytest.raises(AuthError):
        load_token()


def test_load_token_corrupt_file_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bad = tmp_path / "auth.json"
    bad.write_text("{not json")
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    monkeypatch.setattr("vercel_fleet.auth.VERCEL_CLI_AUTH_PATH", bad)
    with pytest.raises(AuthError):
        load_token()


def test_team_id_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL_TEAM_ID", "team_custom")
    assert load_team_id() == "team_custom"


def test_team_id_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERCEL_TEAM_ID", raising=False)
    assert load_team_id() == ""

