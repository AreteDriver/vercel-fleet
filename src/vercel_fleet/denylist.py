from __future__ import annotations

BOT_REFERRERS: dict[str, str] = {
    "apexoo.com": "domain aggregator scraper",
    "vercel.com": "Vercel preview/dashboard self-referral",
    "vercel.app": "preview deploy self-referral",
    "login.eveonline.com": "OAuth callback, not a real visit",
    "yometa.com": "referrer cleaner / privacy proxy",
    "googleusercontent.com": "Google cache/preview",
    "translate.google.com": "translation passthrough",
    "t.co": "raw redirect, no source info",
}


def is_bot(hostname: str) -> tuple[bool, str | None]:
    if not hostname:
        return True, "empty referrer"
    host = hostname.strip().lower().lstrip(".")
    if host in BOT_REFERRERS:
        return True, BOT_REFERRERS[host]
    # Subdomain match: *.vercel.app, *.vercel.com
    for known in BOT_REFERRERS:
        if host.endswith("." + known):
            return True, BOT_REFERRERS[known]
    return False, None


def filter_real(rows: list, key_attr: str = "key") -> list:
    out = []
    for r in rows:
        key = getattr(r, key_attr) if hasattr(r, key_attr) else r.get(key_attr)
        bot, _ = is_bot(str(key or ""))
        if not bot:
            out.append(r)
    return out
