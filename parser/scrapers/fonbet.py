"""Fon.bet live football scraper.

IMPORTANT — Fon.bet's frontend is a heavily obfuscated single-page app and
most of its DOM structure could not be verified from this environment:
this sandbox's egress policy blocks fon.bet outright (confirmed via the
agent proxy status endpoint — a hard "policy denial", not a transient
error). Treat LIVE_ROW_SELECTOR / STATS_TAB_SELECTOR / the text-based stat
fallback as a starting guess, not a working implementation — EXCEPT
corners, which was confirmed against a real devtools inspection (see
below) and should already work as written.

(Flashscore no longer has this problem — see scrapers/flashscore.py, which
uses a verified third-party API instead of scraping. Fon.bet has no
equivalent public API for a single bookmaker's live odds/stats, so this
file still has to drive a real browser.)

Confirmed structure (as of the devtools inspection this was built from):
the match page shows a persistent "scoreboard" widget — no need to click
into any tab — with one flex "column" div per metric (main score, 1st-half
score, corners, ...), each followed by two sibling value divs
(``column_t1--<hash>`` = home, ``column_t2--<hash>`` = away). The corners
column is identified by a descendant ``[resource-name="mcCorner"]`` icon,
a semantic attribute that should be far more stable across redesigns than
the hashed CSS class names. ``_corners_from_scoreboard`` walks from that
icon to the following value divs via XPath rather than hardcoding the
hash suffixes.

The main score's column has NOT been confirmed the same way yet (it was
the leftmost, unlabeled column in the inspected screenshot) — until it is,
``list_live_matches``' score extraction below is still a guess. Everything
else (yellow/red cards, shots, possession) still relies on
``base.parse_stat_row_text`` scanning a "Статистика" tab that was never
confirmed to exist under that exact selector.

Before relying on the unconfirmed parts in production:
  1. Run with HEADLESS=false from a network that can reach fon.bet.
  2. Open devtools on the live-football list and confirm/replace
     LIVE_ROW_SELECTOR, STATS_TAB_SELECTOR, STATS_PANEL_SELECTOR.
  3. The row-text parsing (``base.parse_stat_row_text``) only needs each
     stat row's rendered text, e.g. "5 Угловые 3" — it does not care
     about class names, so it should keep working across redesigns once
     you point it at the right container.
"""

from __future__ import annotations

from playwright.async_api import Browser, Page

from models import MatchRef, MatchStats
from scrapers.base import FONBET_STAT_LABELS, LiveStatsScraper, parse_stat_row_text

LIVE_URL = "https://fon.bet/live?sportId=football"
LIVE_ROW_SELECTOR = "[data-test-id='live-event']"
STATS_TAB_SELECTOR = "text=Статистика"
STATS_PANEL_SELECTOR = "[data-test-id='event-statistics']"

CORNER_ICON_SELECTOR = "[resource-name='mcCorner']"
SCOREBOARD_COLUMN_XPATH = "xpath=ancestor::div[contains(@class, 'column--')][1]"
NEXT_VALUE_XPATH = "xpath=following-sibling::div[contains(@class, '{cls}')][1]"


async def _corners_from_scoreboard(page: Page) -> tuple[float, float] | None:
    """Reads corners off the match page's persistent scoreboard widget,
    anchored on the semantic `resource-name="mcCorner"` icon rather than
    any hashed CSS class (see module docstring)."""
    icon = page.locator(CORNER_ICON_SELECTOR).first
    if not await icon.count():
        return None

    column = icon.locator(SCOREBOARD_COLUMN_XPATH)
    if not await column.count():
        return None

    home_cell = column.locator(NEXT_VALUE_XPATH.format(cls="column_t1"))
    away_cell = column.locator(NEXT_VALUE_XPATH.format(cls="column_t2"))
    if not await home_cell.count() or not await away_cell.count():
        return None

    try:
        home = float((await home_cell.inner_text()).strip())
        away = float((await away_cell.inner_text()).strip())
    except ValueError:
        return None
    return home, away


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

            stats: dict[str, tuple[float, float]] = {}

            # Confirmed selector - no tab click needed, it's on the
            # persistent scoreboard widget. See module docstring.
            corners = await _corners_from_scoreboard(page)
            if corners is not None:
                stats["corners"] = corners

            # Everything else is still an unconfirmed guess (see module
            # docstring) - best-effort, and shouldn't blow up the corners
            # result above if the "Статистика" tab/selector turns out wrong.
            try:
                tab = page.locator(STATS_TAB_SELECTOR).first
                if await tab.count():
                    await tab.click()
                    await page.wait_for_selector(STATS_PANEL_SELECTOR, timeout=15_000)
                    panel_text = await page.locator(STATS_PANEL_SELECTOR).inner_text()
                    lines = [line for line in panel_text.splitlines() if line.strip()]

                    for canonical_name, labels in FONBET_STAT_LABELS.items():
                        if canonical_name in stats:
                            continue
                        for line in lines:
                            parsed = parse_stat_row_text(line, labels)
                            if parsed is not None:
                                stats[canonical_name] = parsed
                                break
            except Exception:
                pass

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
