from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from vercel_fleet.store import Store


@pytest.fixture
def tmp_store(tmp_path: Path) -> Iterator[Store]:
    db = tmp_path / "fleet.db"
    s = Store(db)
    yield s
    s.close()


@pytest.fixture
def fake_auth_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "auth.json"
    p.write_text(json.dumps({"token": "tok_fake_123"}))
    monkeypatch.setattr("vercel_fleet.auth.VERCEL_CLI_AUTH_PATH", p)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    return p


@pytest.fixture
def project_raw() -> dict:
    return {
        "id": "prj_test1",
        "name": "test-project",
        "framework": "nextjs",
        "webAnalytics": {"id": "wa_x", "enabledAt": 123, "hasData": True},
        "speedInsights": {"id": "si_x", "hasData": False},
        "targets": {
            "production": {"alias": ["test-project.aretedriver.dev"]}
        },
    }


@pytest.fixture
def deploy_raw() -> dict:
    return {
        "uid": "dpl_abc",
        "url": "test-project-xxx.vercel.app",
        "state": "READY",
        "readyState": "READY",
        "created": 1779000000000,
        "target": "production",
        "meta": {
            "githubCommitMessage": "feat: add thing",
            "githubCommitSha": "abc123",
        },
    }
