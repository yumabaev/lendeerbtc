from __future__ import annotations

import re
from abc import ABC, abstractmethod

from models import MatchRef, MatchStats

# Canonical stat name -> substrings that identify the row label on fon.bet's
# stats widget (matched case-insensitively). Flashscore no longer needs this:
# it's fetched via a structured API (scrapers/flashscore.py) that returns
# exact field names instead of rendered text rows.
FONBET_STAT_LABELS: dict[str, list[str]] = {
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

    This is intentionally text-based (not CSS-class based): fon.bet's
    frontend restyles/obfuscates class names frequently, but the row's
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
