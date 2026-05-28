from __future__ import annotations

import pytest

from vercel_fleet.denylist import BOT_REFERRERS, filter_real, is_bot


@pytest.mark.parametrize("host", ["apexoo.com", "vercel.com", "yometa.com"])
def test_known_bots(host: str) -> None:
    bot, reason = is_bot(host)
    assert bot is True
    assert reason


def test_subdomain_match() -> None:
    bot, reason = is_bot("foo.vercel.app")
    assert bot is True
    assert reason


def test_real_referrer() -> None:
    bot, reason = is_bot("google.com")
    assert bot is False
    assert reason is None


def test_empty_referrer_is_bot() -> None:
    bot, _ = is_bot("")
    assert bot is True


def test_case_normalization() -> None:
    bot, _ = is_bot("APEXOO.com")
    assert bot is True


def test_leading_dot_stripped() -> None:
    bot, _ = is_bot(".vercel.app")
    assert bot is True


def test_filter_real_on_objects() -> None:
    class R:
        def __init__(self, key: str) -> None:
            self.key = key

    rows = [R("google.com"), R("apexoo.com"), R("github.com"), R("vercel.com")]
    real = filter_real(rows)
    assert len(real) == 2
    assert {r.key for r in real} == {"google.com", "github.com"}


def test_denylist_has_eight_or_more() -> None:
    assert len(BOT_REFERRERS) >= 8
