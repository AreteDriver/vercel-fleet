---
description: Vercel fleet rollup — traffic, deploys, dark projects, bot-filtered referrers across all projects on aretedrivers-projects team. Invoke with /vercel-fleet [subcommand].
---

Run the `vercel-fleet` CLI inline and show the result.

## How to handle `$ARGUMENTS`

| Args | What to run |
|---|---|
| (empty) | `vercel-fleet overview` — default 30d cross-project rollup |
| `sync` | `vercel-fleet sync` — pull fresh data |
| `dark` | `vercel-fleet dark` — projects with no analytics or zero traffic |
| `deploys [--since 7d] [--state ERROR]` | `vercel-fleet deploys $ARGS` |
| `project <name>` | `vercel-fleet project <name>` — single-project drill-down |
| `refs [--include-bots] [--project <name>]` | `vercel-fleet refs $ARGS` |
| `denylist` | `vercel-fleet denylist` — show the bot referrer list |
| `doctor` | `vercel-fleet doctor` — auth, API reach, DB state |
| any other args | Pass through verbatim to `vercel-fleet $ARGUMENTS` |

## Execution

1. Run `vercel-fleet --version` first to confirm the CLI is installed.
   - If not on PATH: tell the user to `pip install -e ~/projects/vercel-fleet` (or `pip install vercel-fleet` once on PyPI), then stop.
2. Run the mapped command. Use `COLUMNS=200 vercel-fleet ...` so rich tables render at full width.
3. If the output mentions "never synced" or shows zero projects, surface that the user needs to run `/vercel-fleet sync` first.
4. If the output contains `Vercel API 403` or `invalidToken`, point the user at the auth setup in `~/projects/vercel-fleet/README.md` — Personal Access Token, not the CLI session token.

## Output

Show the CLI output verbatim. Do not paraphrase, summarize, or restructure. Only add a one-line context note at the end if there's an actionable next step (e.g., "→ run `/vercel-fleet sync` then re-check").

## What this is

A thin slash-command wrapper around the `vercel-fleet` Python CLI at `~/projects/vercel-fleet/`. The CLI:
- Pulls projects + 30-day analytics + recent deploys from Vercel REST API
- Stores snapshot in SQLite at `~/.local/share/vercel-fleet/fleet.db`
- Filters bot referrers (apexoo, vercel.com self-refs, eveonline OAuth, etc.)
- Powered by a systemd-user timer that runs `sync` every 15 minutes once installed via `/vercel-fleet install-timer`

## Common follow-ups inside one session

After running `/vercel-fleet`, the user often wants to drill into a specific project. When they ask "what about benchgoblins?" or similar, just call `vercel-fleet project benchgoblins` — no need to re-invoke the slash command.
