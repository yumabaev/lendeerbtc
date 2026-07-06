"""Pure-Python pairing confirmation and alert dedupe — no Playwright dependency,
so this logic can be unit-tested and dry-run without a browser or network."""

from __future__ import annotations

from models import Discrepancy, MatchedPair

MINUTE_TOLERANCE = 3


def _parse_minute(raw: str) -> int | None:
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else None


def confirmed(pair: MatchedPair) -> bool:
    """Corroborates a name-based pairing with live score/minute before trusting it.

    Team-name similarity alone is not enough to safely pair events across a
    Latin-script and a Cyrillic-script source, so any pair whose current
    score or elapsed minute clearly disagree is dropped rather than fed
    into stat comparison (which would just produce noise from a bad pairing).
    """
    fs, fb = pair.flashscore, pair.fonbet
    if fs.score_home is not None and fb.score_home is not None:
        if (fs.score_home, fs.score_away) != (fb.score_home, fb.score_away):
            return False
    fs_minute, fb_minute = _parse_minute(fs.minute), _parse_minute(fb.minute)
    if fs_minute is not None and fb_minute is not None:
        if abs(fs_minute - fb_minute) > MINUTE_TOLERANCE:
            return False
    return True


class DiscrepancyState:
    """Suppresses repeat alerts for the same (match, stat) unless the values changed."""

    def __init__(self) -> None:
        self._seen: dict[tuple[str, str, str], tuple[float, float, float, float]] = {}

    def is_new(self, disc: Discrepancy) -> bool:
        key = (disc.pair.flashscore.match_id, disc.pair.fonbet.match_id, disc.stat_name)
        value = disc.flashscore_value + disc.fonbet_value
        if self._seen.get(key) == value:
            return False
        self._seen[key] = value
        return True
