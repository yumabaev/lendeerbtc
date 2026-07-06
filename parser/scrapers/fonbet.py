"""Fon.bet live football scraper.

IMPORTANT: fon.bet actively blocks automated browser access with an
anti-bot wall (a "Forbidden" page with a bot-check report ID, confirmed by
running this scraper for real) — it is not just a matter of fixing
selectors. This module is kept for reference/URL-pinning only; the
running pipeline (see main.py) uses scrapers/pari.py instead, which shares
the exact same frontend markup (confirmed via devtools) but did not show
this block. Do not attempt to defeat fon.bet's bot detection (fingerprint
spoofing, proxy rotation, stealth patches, etc.) — see the chat history
for why.

All scraping logic is shared with pari.ru and lives in
scrapers.base.BettingPlatformScraper (corners confirmed two ways there;
match identity extraction and other stats are still unconfirmed guesses,
per that module's docstring).
"""

from __future__ import annotations

from scrapers.base import BettingPlatformScraper


class FonbetScraper(BettingPlatformScraper):
    source_name = "fonbet"
    live_url = "https://fon.bet/live/football"

    def match_url(self, match_id: str) -> str:
        return f"https://fon.bet/live/{match_id}"
