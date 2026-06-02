# vercel-fleet

Cross-project Vercel analytics rollup. Native Vercel UI is per-project — `vercel-fleet` rolls everything up: traffic, deploys, dark (no-analytics) projects, bot-filtered referrers, build state. One terminal table. Local SQLite snapshot. systemd-user timer keeps it fresh.

## Why

Vercel's dashboard answers "how is *this* project doing?" `vercel-fleet` answers "how is *my whole fleet* doing?" — which projects ship, which are dark, which referrers are real vs scraper noise.

## Install

```bash
pip install vercel-fleet          # CLI only
pip install vercel-fleet[mcp]     # CLI + MCP server

# or, from source
git clone https://github.com/AreteDriver/vercel-fleet && cd vercel-fleet
pipx install --editable ".[mcp]"  # adds vercel-fleet AND vercel-fleet-mcp to PATH
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

## Claude Code slash-command

`.claude/commands/vercel-fleet.md` ships a `/vercel-fleet` slash-command that wraps the CLI inline — it maps `$ARGUMENTS` to the right subcommand and shows the output verbatim. Install by symlinking it into your user commands dir (keeps it tracked here, no drift):

```bash
ln -s ~/projects/vercel-fleet/.claude/commands/vercel-fleet.md ~/.claude/commands/vercel-fleet.md
```

Then `/vercel-fleet`, `/vercel-fleet sync`, `/vercel-fleet project <name>`, etc. The command requires the `vercel-fleet` CLI on PATH (`pip install -e .`).

## Claude Code MCP server

`vercel-fleet[mcp]` ships an MCP stdio server that exposes the same data as JSON-returning tools, so Claude Code can compose fleet data with anything else in a session.

Register:

```bash
claude mcp add vercel-fleet -- /home/$USER/.local/bin/vercel-fleet-mcp
claude mcp list  # vercel-fleet: ✓ Connected
```

Tools exposed:

| Tool | Returns |
|---|---|
| `overview` | Fleet rollup: totals, live projects, anomalies |
| `project(name)` | Drill-down: top pages, refs (tagged bot/real), countries, devices, deploys |
| `dark` | Projects with analytics disabled or zero traffic |
| `deploys(since?, state?, limit?)` | Fleet-wide deploys |
| `refs(project?, include_bots?)` | Referrer hostnames |
| `last_sync` | Freshness check — when, age, errors |
| `sync` | Pull fresh data from Vercel API (~30s) |
| `denylist` | Bot referrer denylist |

All tools return JSON. Compose queries like *"compare top 3 projects' real-referrer views with their last-deploy ages"* — Claude calls `overview`, then `project` for each, joins the results.

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
pytest                    # 79 tests
pytest --cov=vercel_fleet # ≥80% coverage
ruff check src tests
```

## License

MIT
