from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rich.console import Console

SERVICE = """[Unit]
Description=Vercel fleet analytics snapshot (vercel-fleet sync)

[Service]
Type=oneshot
ExecStart={exe} sync --quiet
Nice=10
IOSchedulingClass=idle
"""

TIMER = """[Unit]
Description=Run vercel-fleet sync every 15 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true
Unit=vercel-fleet-sync.service

[Install]
WantedBy=timers.target
"""


def install(console: Console) -> int:
    exe = shutil.which("vercel-fleet")
    if not exe:
        console.print(
            "[red]vercel-fleet not on PATH — install it first "
            "(`pipx install vercel-fleet` or `pip install -e .`)[/red]"
        )
        return 1

    unit_dir = Path.home() / ".config/systemd/user"
    unit_dir.mkdir(parents=True, exist_ok=True)

    service_path = unit_dir / "vercel-fleet-sync.service"
    timer_path = unit_dir / "vercel-fleet-sync.timer"

    service_path.write_text(SERVICE.format(exe=exe))
    timer_path.write_text(TIMER)

    console.print(f"[green]✓[/green] Wrote {service_path}")
    console.print(f"[green]✓[/green] Wrote {timer_path}")

    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", "vercel-fleet-sync.timer"],
            check=True,
        )
        console.print(
            "[green]✓[/green] Enabled vercel-fleet-sync.timer "
            "(runs every 15min, first run in ~2min)"
        )
    except FileNotFoundError:
        console.print("[yellow]systemctl not available — units written but not enabled[/yellow]")
        return 0
    except subprocess.CalledProcessError as e:
        console.print(f"[red]systemctl error: {e}[/red]")
        return 1

    return 0
