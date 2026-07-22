from __future__ import annotations

import json
import os
from pathlib import Path


class AuthError(RuntimeError):
    pass


VERCEL_CLI_AUTH_PATH = Path.home() / ".local/share/com.vercel.cli/auth.json"


def load_token() -> str:
    env_token = os.environ.get("VERCEL_TOKEN")
    if env_token:
        return env_token.strip()

    if not VERCEL_CLI_AUTH_PATH.exists():
        raise AuthError(
            "No VERCEL_TOKEN set and no Vercel CLI auth file at "
            f"{VERCEL_CLI_AUTH_PATH}. Run `vercel login` or export VERCEL_TOKEN."
        )

    try:
        data = json.loads(VERCEL_CLI_AUTH_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthError(f"Could not read Vercel CLI auth file: {exc}") from exc

    token = data.get("token")
    if not token:
        raise AuthError(f"No token in {VERCEL_CLI_AUTH_PATH}")
    return token


def load_team_id() -> str:
    return os.environ.get("VERCEL_TEAM_ID", "")

