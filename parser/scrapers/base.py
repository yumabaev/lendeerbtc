from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod

from playwright.async_api import Browser, BrowserContext, Locator, Page

from models import MatchRef, MatchStats

# Canonical stat name -> substrings that identify the row label on the
# bookmaker's "Статистика" tab (matched case-insensitively). Flashscore
# doesn't need this: it's fetched via a structured API
# (scrapers/flashscore.py) that returns exact field names instead of
# rendered text rows.
RU_BOOKMAKER_STAT_LABELS: dict[str, list[str]] = {
    "corners": ["угловые"],
    "yellow_cards": ["жёлтые карточки", "желтые карточки"],
    "red_cards": ["красные карточки"],
    "shots_on_target": ["удары в створ"],
    "shots_off_target": ["удары мимо"],
    "possession": ["владение мячом"],
    "attacks": ["опасные атаки"],
}

_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?\s*%?")


def parse_stat_row_text(row_text: str, label_substrings: list[str]) -> tuple[float, float] | None:
    """Given the full text of one stat row (e.g. "5 Угловые 3" or
    "56% Владение мячом 44%"), extract (home_value, away_value) if the row
    matches one of the given label substrings.

    This is intentionally text-based (not CSS-class based): these sites'
    frontends restyle/obfuscate class names frequently, but the row's
    visible text layout (home value, label, away value) is stable.
    """
    lowered = row_text.lower()
    if not any(label in lowered for label in label_substrings):
        return None

    numbers = _NUMBER_RE.findall(row_text)
    if len(numbers) < 2:
        return None

    def to_float(raw: str) -> float:
        return float(raw.replace(",", ".").replace("%", "").strip())

    return to_float(numbers[0]), to_float(numbers[-1])


class LiveStatsScraper(ABC):
    source_name: str

    @abstractmethod
    async def list_live_matches(self) -> list[MatchRef]:
        """Return all currently live matches for the sport (football only, for now)."""

    @abstractmethod
    async def get_match_stats(self, ref: MatchRef) -> MatchStats:
        """Fetch/scrape a match's live stats and return canonical stat values."""


# --- Shared implementation for the fon.bet/pari.ru betting platform -------
#
# fon.bet and pari.ru were confirmed via devtools inspection to share
# identical (obfuscated) frontend markup - same class-name prefixes for
# everything below - strongly suggesting the same underlying platform/tech
# provider. This is where that shared, confirmed logic lives; subclasses
# in scrapers/fonbet.py and scrapers/pari.py only pin the domain-specific
# URLs.
#
# Confirmed structure #1 - corners directly in the live list (preferred,
# no per-match navigation needed): the live-football list renders each
# match as a `[class*="sport-base-event-wrap"]` block; a football match
# commonly shows one sub-event row inline with the main score without
# needing to click "Показать ещё N подсобытий" - a
# `[class*="sport-sub-event-name"]` div whose text is exactly "угловые",
# sharing a `sport-base-event__main_caption` container with a sibling
# `[class*="event-block-score"]` span formatted "H:A" (e.g. "0:8"). Read
# by ``corners_from_list_row``, cached per match_id during
# ``BettingPlatformScraper.list_live_matches`` so ``get_match_stats``
# doesn't need to hit the match page at all when the cache has it.
#
# Confirmed structure #2 - corners via the per-match scoreboard widget
# (fallback, used only if a match's corners sub-event wasn't visible in
# the list scan): the match page shows a persistent "scoreboard" widget -
# no tab click needed - with one flex "column" div per metric (main
# score, 1st-half score, corners, ...). Each column div has, as direct
# children: an optional ``column__caption--<hash>`` (label/icon) and two
# value divs (``column_t1--<hash>`` = home, ``column_t2--<hash>`` = away).
# The corners column is identified by a *descendant*
# ``[resource-name="mcCorner"]`` icon inside its caption - a semantic
# attribute that should be far more stable across redesigns than the
# hashed CSS classes. ``corners_from_scoreboard`` walks from that icon up
# to its enclosing column div, then reads that column's own
# `column_t1`/`column_t2` children.
#
# Match identity (team names, main score, elapsed minute, match_id) is
# STILL an unconfirmed guess in ``BettingPlatformScraper.list_live_matches``
# below - it hasn't been checked against real devtools output the way
# corners has. Everything else (yellow/red cards, shots, possession) still
# relies on ``parse_stat_row_text`` scanning a "Статистика" tab that was
# never confirmed to exist under that exact selector.

LIVE_ROW_SELECTOR = "[class*='sport-base-event-wrap']"
STATS_TAB_SELECTOR = "text=Статистика"
STATS_PANEL_SELECTOR = "[data-test-id='event-statistics']"

CORNER_ICON_SELECTOR = "[resource-name='mcCorner']"
SCOREBOARD_COLUMN_XPATH = "xpath=ancestor::div[contains(@class, 'column--')][1]"

SUBEVENT_NAME_SELECTOR = "[class*='sport-sub-event-name']"
SUBEVENT_SCORE_SELECTOR = "[class*='event-block-score']"
CORNERS_SUBEVENT_LABEL = "угловые"


async def corners_from_list_row(row: Locator) -> tuple[float, float] | None:
    """Reads corners straight from the live list's inline "угловые"
    sub-event row for this match, if one is visible without needing to
    expand "Показать ещё N подсобытий". Returns None if this match's row
    doesn't show a corners sub-event inline - callers should fall back to
    ``corners_from_scoreboard``."""
    labels = row.locator(SUBEVENT_NAME_SELECTOR)
    count = await labels.count()
    for i in range(count):
        label = labels.nth(i)
        text = (await label.inner_text()).strip().lower()
        if text != CORNERS_SUBEVENT_LABEL:
            continue

        caption = label.locator("xpath=..")
        score_el = caption.locator(SUBEVENT_SCORE_SELECTOR).first
        if not await score_el.count():
            return None

        score_text = (await score_el.inner_text()).strip()
        parts = score_text.replace(" ", "").split(":")
        if len(parts) != 2:
            return None
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            return None
    return None


async def corners_from_scoreboard(page: Page) -> tuple[float, float] | None:
    """Reads corners off the match page's persistent scoreboard widget,
    anchored on the semantic `resource-name="mcCorner"` icon rather than
    any hashed CSS class. Fallback for when ``corners_from_list_row``
    didn't find an inline sub-event."""
    icon = page.locator(CORNER_ICON_SELECTOR).first
    if not await icon.count():
        return None

    column = icon.locator(SCOREBOARD_COLUMN_XPATH)
    if not await column.count():
        return None

    home_cell = column.locator("[class*='column_t1']")
    away_cell = column.locator("[class*='column_t2']")
    if not await home_cell.count() or not await away_cell.count():
        return None

    try:
        home = float((await home_cell.first.inner_text()).strip())
        away = float((await away_cell.first.inner_text()).strip())
    except ValueError:
        return None
    return home, away


async def _try_inner_text(locator) -> str | None:
    try:
        if await locator.count():
            return (await locator.first.inner_text()).strip()
    except Exception:
        pass
    return None


# Confirmed via a real run: the actual separator between team names is an
# em dash ("—", U+2014), e.g. "Партизан Белград — Нефтчи Баку" - not a
# plain hyphen or en dash as originally guessed. Only the row's FIRST line
# is checked (not the whole row's blobbed text, which also contains
# scores/odds/sub-market rows) - this doubles as a filter for non-match
# rows (sub-market rows like "угловые" or "1-й тайм" have no separator in
# their first line and are skipped).
_TEAM_SEPARATORS = (" — ", " – ", " - ")


def _split_teams(text: str) -> tuple[str, str]:
    first_line = text.split("\n", 1)[0].strip()
    for sep in _TEAM_SEPARATORS:
        if sep in first_line:
            parts = [p.strip() for p in first_line.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts[0], parts[1]
    return "", ""


class BettingPlatformScraper(LiveStatsScraper):
    """Base for fon.bet/pari.ru-family sites. Subclasses set `live_url`
    and implement `match_url`.

    Keeps ONE browser context (and its cookies/session) alive across the
    whole run instead of opening and tearing down a fresh context on every
    poll cycle - cheaper, and avoids the browser window flashing open/
    closed repeatedly. Each call still opens its own page (tab) so
    concurrent get_match_stats() calls (one per matched pair) don't race
    each other navigating the same page; only the tab is closed when a
    call finishes, the shared context stays open until ``close()`` is
    called (or the underlying browser itself is closed)."""

    live_url: str

    def __init__(self, browser: Browser):
        self._browser = browser
        self._context: BrowserContext | None = None
        self._context_lock = asyncio.Lock()
        # match_id -> corners, populated opportunistically by
        # list_live_matches() from the inline list-page sub-event row so
        # get_match_stats() can skip visiting the match page entirely when
        # it's there. Only valid for the poll cycle that populated it.
        self._corners_cache: dict[str, tuple[float, float]] = {}

    def match_url(self, match_id: str) -> str:
        raise NotImplementedError

    async def _get_context(self) -> BrowserContext:
        if self._context is None:
            async with self._context_lock:
                if self._context is None:
                    self._context = await self._browser.new_context()
        return self._context

    async def close(self) -> None:
        """Closes the shared context/window. Call when fully done (e.g.
        on shutdown) - not needed between poll cycles."""
        if self._context is not None:
            await self._context.close()
            self._context = None

    async def list_live_matches(self) -> list[MatchRef]:
        # The scraper instance now persists across poll cycles (see
        # module docstring), so the cache must be reset each scan or it'd
        # keep serving stale corners from a previous cycle.
        self._corners_cache.clear()

        context = await self._get_context()
        page = await context.new_page()
        try:
            await page.goto(self.live_url, wait_until="domcontentloaded")
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

                corners = await corners_from_list_row(row)
                if corners is not None:
                    self._corners_cache[match_id] = corners

                matches.append(
                    MatchRef(
                        source=self.source_name,
                        match_id=match_id,
                        url=self.match_url(match_id),
                        home_team=home,
                        away_team=away,
                        minute=minute,
                        score_home=score_home,
                        score_away=score_away,
                    )
                )
            return matches
        finally:
            await page.close()

    async def get_match_stats(self, ref: MatchRef) -> MatchStats:
        stats: dict[str, tuple[float, float]] = {}

        cached_corners = self._corners_cache.get(ref.match_id)
        if cached_corners is not None:
            stats["corners"] = cached_corners

        context = await self._get_context()
        page = await context.new_page()
        try:
            await page.goto(ref.url, wait_until="domcontentloaded")

            # Fallback: this match's corners weren't visible inline in the
            # list scan (e.g. hidden behind "Показать ещё N подсобытий").
            if "corners" not in stats:
                corners = await corners_from_scoreboard(page)
                if corners is not None:
                    stats["corners"] = corners

            # Everything else is still an unconfirmed guess - best-effort,
            # and shouldn't blow up the corners result above if the
            # "Статистика" tab/selector turns out wrong.
            try:
                tab = page.locator(STATS_TAB_SELECTOR).first
                if await tab.count():
                    await tab.click()
                    await page.wait_for_selector(STATS_PANEL_SELECTOR, timeout=15_000)
                    panel_text = await page.locator(STATS_PANEL_SELECTOR).inner_text()
                    lines = [line for line in panel_text.splitlines() if line.strip()]

                    for canonical_name, labels in RU_BOOKMAKER_STAT_LABELS.items():
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
            await page.close()
