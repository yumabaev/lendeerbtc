from __future__ import annotations

import re
from abc import ABC, abstractmethod

from playwright.async_api import Page

from models import MatchRef, MatchStats

# Canonical stat name -> list of substrings that identify the row label on
# each source's stats widget (matched case-insensitively).
STAT_LABELS: dict[str, dict[str, list[str]]] = {
    "corners": {
        "flashscore": ["corner kicks", "corners"],
        "fonbet": ["угловые"],
    },
    "yellow_cards": {
        "flashscore": ["yellow cards"],
        "fonbet": ["жёлтые карточки", "желтые карточки"],
    },
    "red_cards": {
        "flashscore": ["red cards"],
        "fonbet": ["красные карточки"],
    },
    "shots_on_target": {
        "flashscore": ["shots on target", "shots on goal"],
        "fonbet": ["удары в створ"],
    },
    "shots_off_target": {
        "flashscore": ["shots off target", "shots off goal"],
        "fonbet": ["удары мимо"],
    },
    "possession": {
        "flashscore": ["ball possession", "possession"],
        "fonbet": ["владение мячом"],
    },
    "attacks": {
        "flashscore": ["dangerous attacks"],
        "fonbet": ["опасные атаки"],
    },
}

_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?\s*%?")


def parse_stat_row_text(row_text: str, label_substrings: list[str]) -> tuple[float, float] | None:
    """Given the full text of one stat row (e.g. "5 Corner Kicks 3" or
    "56% Ball Possession 44%"), extract (home_value, away_value) if the row
    matches one of the given label substrings.

    This is intentionally text-based (not CSS-class based): Flashscore and
    Fon.bet both restyle/obfuscate their class names frequently, but the
    row's visible text layout (home value, label, away value) is stable.
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
    async def list_live_matches(self, page: Page) -> list[MatchRef]:
        """Return all currently live matches for the sport (football only, for now)."""

    @abstractmethod
    async def get_match_stats(self, page: Page, ref: MatchRef) -> MatchStats:
        """Navigate to a match's live-stats view and extract canonical stats."""
