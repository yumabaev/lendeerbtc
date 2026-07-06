"""Pari.ru live football scraper.

pari.ru shares the exact same frontend markup as fon.bet (identical
obfuscated class-name prefixes, confirmed via devtools on both) — likely
the same underlying betting platform/tech provider. Unlike fon.bet, it did
NOT show an anti-bot "Forbidden" wall when loaded in a real browser, so
it's used as the running pipeline's second data source instead (see
main.py). All shared scraping logic lives in
scrapers.base.BettingPlatformScraper; this module only pins pari.ru's
URLs.

`match_url` (used to build the per-match page URL from a match_id) has
NOT been independently confirmed for pari.ru — it mirrors fon.bet's
pattern, which was itself never confirmed either (match identity
extraction is still a guess, per the base module's docstring). Verify
with HEADLESS=false before relying on it.
"""

from __future__ import annotations

from scrapers.base import BettingPlatformScraper


class PariScraper(BettingPlatformScraper):
    source_name = "pari"
    live_url = "https://pari.ru/live/football"

    def match_url(self, match_id: str) -> str:
        return f"https://pari.ru/live/{match_id}"
