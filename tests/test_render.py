from __future__ import annotations

from vercel_fleet.render import relative_time, sparkline, state_style


def test_sparkline_basic() -> None:
    out = sparkline([1, 2, 4, 8], width=4)
    assert len(out) == 4
    assert out[-1] == "█"


def test_sparkline_pads_short() -> None:
    out = sparkline([5], width=5)
    assert len(out) == 5
    assert out[-1] == "█"


def test_sparkline_empty() -> None:
    assert sparkline([], width=3) == "   "


def test_sparkline_all_zero() -> None:
    out = sparkline([0, 0, 0], width=3)
    assert out == "▁▁▁"


def test_relative_time_zero() -> None:
    assert relative_time(0) == "—"


def test_relative_time_seconds() -> None:
    import time
    now_ms = int(time.time() * 1000)
    out = relative_time(now_ms - 5000)
    assert "s ago" in out or out == "just now"


def test_state_style_known() -> None:
    assert state_style("READY") == "green"
    assert state_style("ERROR") == "red"
    assert state_style("BUILDING") == "yellow"


def test_state_style_unknown() -> None:
    assert state_style("WAT") == "white"
