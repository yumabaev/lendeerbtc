"""Flashscore live football scraper.

IMPORTANT — selectors below are a best effort based on Flashscore's public
markup conventions (``event__match`` rows, ``.stat__category`` rows on the
match-statistics tab) and have NOT been verified against the live site from
this environment: this sandbox's egress policy blocks flashscore.com
outright, so there was no way to load the real page and confirm the DOM.
Flashscore also redesigns this markup periodically. Before relying on this
in production:

  1. Run with HEADLESS=false once, open devtools, and confirm the
     selectors in LIVE_ROW_SELECTOR / STAT_ROW_SELECTOR still match.
  2. If they don't, update just the selectors below — the row-text
     parsing in ``base.parse_stat_row_text`` is selector-agnostic and
     shouldn't need touching.
"""

from __future__ import annotations

import re

from playwright.async_api import Page

from models import MatchRef, MatchStats
from scrapers.base import LiveStatsScraper, STAT_LABELS, parse_stat_row_text

LIVE_URL = "https://www.flashscore.com/football/"
LIVE_ROW_SELECTOR = "div.event__match--live"
STAT_ROW_SELECTOR = ".stat__row"

_SCORE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


class FlashscoreScraper(LiveStatsScraper):
    source_name = "flashscore"

    async def list_live_matches(self, page: Page) -> list[MatchRef]:
        await page.goto(LIVE_URL, wait_until="domcontentloaded")
        await page.wait_for_selector(LIVE_ROW_SELECTOR, timeout=15_000)

        rows = page.locator(LIVE_ROW_SELECTOR)
        count = await rows.count()

        matches: list[MatchRef] = []
        for i in range(count):
            row = rows.nth(i)
            match_id = await row.get_attribute("id")
            if not match_id:
                continue
            match_id = match_id.split("_")[-1]

            home = (await row.locator(".event__participant--home").inner_text()).strip()
            away = (await row.locator(".event__participant--away").inner_text()).strip()
            minute = (await row.locator(".event__stage--block").inner_text()).strip()

            score_home = score_away = None
            try:
                home_score_text = await row.locator(".event__score--home").inner_text()
                away_score_text = await row.locator(".event__score--away").inner_text()
                score_home = int(home_score_text.strip())
                score_away = int(away_score_text.strip())
            except Exception:
                pass

            matches.append(
                MatchRef(
                    source=self.source_name,
                    match_id=match_id,
                    url=f"https://www.flashscore.com/match/{match_id}/#/match-summary/match-statistics/0",
                    home_team=home,
                    away_team=away,
                    minute=minute,
                    score_home=score_home,
                    score_away=score_away,
                )
            )
        return matches

    async def get_match_stats(self, page: Page, ref: MatchRef) -> MatchStats:
        await page.goto(ref.url, wait_until="domcontentloaded")
        await page.wait_for_selector(STAT_ROW_SELECTOR, timeout=15_000)

        rows = page.locator(STAT_ROW_SELECTOR)
        count = await rows.count()
        row_texts = [await rows.nth(i).inner_text() for i in range(count)]

        stats: dict[str, tuple[float, float]] = {}
        for canonical_name, labels_by_source in STAT_LABELS.items():
            labels = labels_by_source["flashscore"]
            for text in row_texts:
                parsed = parse_stat_row_text(text, labels)
                if parsed is not None:
                    stats[canonical_name] = parsed
                    break

        return MatchStats(ref=ref, stats=stats)
