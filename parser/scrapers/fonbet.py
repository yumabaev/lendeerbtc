"""Fon.bet live football scraper.

IMPORTANT — Fon.bet's frontend is a heavily obfuscated single-page app and
its DOM structure could not be verified from this environment: this
sandbox's egress policy blocks fon.bet outright (confirmed via the agent
proxy status endpoint — a hard "policy denial", not a transient error), so
none of the selectors below have ever been checked against a real page.
Treat everything in LIVE_ROW_SELECTOR / STATS_TAB_SELECTOR / stat-row
lookup as a starting guess, not a working implementation.

(Flashscore no longer has this problem — see scrapers/flashscore.py, which
uses a verified third-party API instead of scraping. Fon.bet has no
equivalent public API for a single bookmaker's live odds/stats, so this
file still has to drive a real browser.)

Before relying on this in production:
  1. Run with HEADLESS=false from a network that can reach fon.bet.
  2. Open devtools on the live-football list and on a match's
     "Статистика" tab, and replace the selectors below with the real
     ones.
  3. The row-text parsing (``base.parse_stat_row_text``) only needs each
     stat row's rendered text, e.g. "5 Угловые 3" — it does not care
     about class names, so it should keep working across redesigns once
     you point it at the right container.

To reduce how much depends on exact class names, ``get_match_stats``
falls back to scanning the whole stats-panel text line by line for the
known Russian labels in ``scrapers.base.FONBET_STAT_LABELS`` rather than
requiring one row-per-stat selector to exist.
"""

from __future__ import annotations

from playwright.async_api import Browser

from models import MatchRef, MatchStats
from scrapers.base import FONBET_STAT_LABELS, LiveStatsScraper, parse_stat_row_text

LIVE_URL = "https://fon.bet/live?sportId=football"
LIVE_ROW_SELECTOR = "[data-test-id='live-event']"
STATS_TAB_SELECTOR = "text=Статистика"
STATS_PANEL_SELECTOR = "[data-test-id='event-statistics']"


class FonbetScraper(LiveStatsScraper):
    source_name = "fonbet"

    def __init__(self, browser: Browser):
        self._browser = browser

    async def list_live_matches(self) -> list[MatchRef]:
        context = await self._browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(LIVE_URL, wait_until="domcontentloaded")
            await page.wait_for_selector(LIVE_ROW_SELECTOR, timeout=15_000)

            rows = page.locator(LIVE_ROW_SELECTOR)
            count = await rows.count()

            matches: list[MatchRef] = []
            for i in range(count):
                row = rows.nth(i)
                match_id = await row.get_attribute("data-event-id")
                if not match_id:
                    match_id = f"row-{i}"

                teams_text = (await row.inner_text()).strip()
                home, away = _split_teams(teams_text)
                if not home or not away:
                    continue

                score_home = score_away = None
                score_text = await _try_inner_text(row.locator("[data-test-id='event-score']"))
                if score_text:
                    parts = score_text.replace(":", "-").split("-")
                    if len(parts) == 2 and all(p.strip().isdigit() for p in parts):
                        score_home, score_away = int(parts[0]), int(parts[1])

                minute = await _try_inner_text(row.locator("[data-test-id='event-time']")) or ""

                matches.append(
                    MatchRef(
                        source=self.source_name,
                        match_id=match_id,
                        url=f"https://fon.bet/live/{match_id}",
                        home_team=home,
                        away_team=away,
                        minute=minute,
                        score_home=score_home,
                        score_away=score_away,
                    )
                )
            return matches
        finally:
            await context.close()

    async def get_match_stats(self, ref: MatchRef) -> MatchStats:
        context = await self._browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(ref.url, wait_until="domcontentloaded")

            tab = page.locator(STATS_TAB_SELECTOR).first
            if await tab.count():
                await tab.click()

            await page.wait_for_selector(STATS_PANEL_SELECTOR, timeout=15_000)
            panel_text = await page.locator(STATS_PANEL_SELECTOR).inner_text()
            lines = [line for line in panel_text.splitlines() if line.strip()]

            stats: dict[str, tuple[float, float]] = {}
            for canonical_name, labels in FONBET_STAT_LABELS.items():
                for line in lines:
                    parsed = parse_stat_row_text(line, labels)
                    if parsed is not None:
                        stats[canonical_name] = parsed
                        break

            return MatchStats(ref=ref, stats=stats)
        finally:
            await context.close()


async def _try_inner_text(locator) -> str | None:
    try:
        if await locator.count():
            return (await locator.first.inner_text()).strip()
    except Exception:
        pass
    return None


def _split_teams(text: str) -> tuple[str, str]:
    for sep in (" - ", " – ", "\n"):
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts[0], parts[1]
    return "", ""
