# vercel-fleet

Cross-project Vercel analytics rollup. Native Vercel UI is per-project — `vercel-fleet` rolls everything up: traffic, deploys, dark (no-analytics) projects, bot-filtered referrers, build state. One terminal table. Local SQLite snapshot. systemd-user timer keeps it fresh.

## Why

Vercel's dashboard answers "how is *this* project doing?" `vercel-fleet` answers "how is *my whole fleet* doing?" — which projects ship, which are dark, which referrers are real vs scraper noise.

## Install

```bash
pip install vercel-fleet
# or, from source
git clone https://github.com/AreteDriver/vercel-fleet && cd vercel-fleet
pip install -e .
```

## Auth

The Vercel CLI session token (`~/.local/share/com.vercel.cli/auth.json`) works **but rotates** on OAuth refresh, which causes intermittent 403s. **Recommended**: create a Personal Access Token.

1. Go to https://vercel.com/account/settings/tokens
2. Create a token (scope: read-only is sufficient)
3. Add to your shell config:

   ```bash
   export VERCEL_TOKEN=...
   export VERCEL_TEAM_ID=team_xxx   # only if not on aretedrivers-projects
   ```

Verify:

```bash
vercel-fleet doctor
```

## Quickstart

```bash
vercel-fleet sync       # pull fresh data from Vercel API
vercel-fleet overview   # 30-day rollup table
vercel-fleet dark       # projects with no analytics or zero traffic
vercel-fleet deploys --since 7d --state ERROR
vercel-fleet project benchgoblins
vercel-fleet refs --include-bots
```

## Daily refresh

Install the systemd-user timer (runs `sync` every 15 minutes):

```bash
vercel-fleet install-timer
systemctl --user list-timers | grep vercel-fleet
```

## Commands

| Command | Purpose |
|---|---|
| `sync` | Pull projects, deployments, and 30-day analytics for all projects, upsert SQLite. |
| `overview` | Cross-project table sorted by views. Hides dark projects. |
| `dark` | Lists projects with analytics disabled or zero views. |
| `deploys` | Fleet-wide deployments. Filter `--since 7d`, `--state ERROR`. |
| `project <name>` | Drill into one project: top pages, refs, countries, devices, deploys. |
| `refs` | Referrers across the fleet. Real-only by default; `--include-bots` to see all. |
| `denylist` | Show the bot referrer denylist with reasons. |
| `doctor` | Check token, API reach, DB state. |
| `install-timer` | Install + enable the systemd-user timer. |

## Bot referrer denylist

`vercel-fleet` filters noise referrers out of "real referrer" columns. Current list:

| Hostname | Reason |
|---|---|
| `apexoo.com` | domain aggregator scraper |
| `vercel.com` / `*.vercel.com` | Vercel preview/dashboard self-referral |
| `*.vercel.app` | preview deploy self-referral |
| `login.eveonline.com` | OAuth callback, not a real visit |
| `yometa.com` | referrer cleaner / privacy proxy |
| `googleusercontent.com` | Google cache/preview |
| `translate.google.com` | translation passthrough |
| `t.co` | raw redirect, no source info |

Customize by editing `src/vercel_fleet/denylist.py`.

## Storage

SQLite at `~/.local/share/vercel-fleet/fleet.db`. Five tables: `projects`, `traffic_top`, `deployments`, `sync_log`, plus migration tracking via `PRAGMA user_version`. Safe to delete and re-`sync`.

## API surface used

| Endpoint | Purpose |
|---|---|
| `GET /v9/projects` | Project list + analytics enablement flags |
| `GET /web-analytics/stats` | Top values per dimension (path, referrer, country, device) |
| `GET /v6/deployments` | Recent deploys, state, commit metadata |

Speed Insights and Usage/cost APIs are not yet supported (no public REST endpoints as of v0.1).

## Development

```bash
pip install -e ".[dev]"
pytest                    # 59 tests
pytest --cov=vercel_fleet # ≥82% coverage
ruff check src tests
```

## License

MIT
