"""Compares live stats between a matched Flashscore/Fon.bet pair."""

from __future__ import annotations

from models import Discrepancy, MatchedPair, MatchStats

# Default tolerance per canonical stat: an absolute difference at or below
# this value is considered normal feed lag/rounding, not a discrepancy.
DEFAULT_TOLERANCES: dict[str, float] = {
    "corners": 1,
    "yellow_cards": 0,
    "red_cards": 0,
    "shots_on_target": 1,
    "shots_off_target": 1,
    "possession": 5,   # percentage points
    "attacks": 3,
}

MINUTE_TOLERANCE = 3        # minutes of live-feed lag considered acceptable
SCORE_MUST_MATCH = True     # refuse to compare stats if scores disagree


def scores_agree(flashscore: MatchStats, fonbet: MatchStats) -> bool:
    fs, fb = flashscore.ref, fonbet.ref
    if fs.score_home is None or fb.score_home is None:
        return True  # can't check, don't block on it
    return (fs.score_home, fs.score_away) == (fb.score_home, fb.score_away)


def compare(
    pair: MatchedPair,
    flashscore: MatchStats,
    fonbet: MatchStats,
    tolerances: dict[str, float] | None = None,
) -> list[Discrepancy]:
    """Returns discrepancies for stats present on both sides beyond tolerance.

    If the current score disagrees between sources, comparison is skipped
    entirely (SCORE_MUST_MATCH) since that almost always means the two
    events are out of sync (feed lag) or were paired incorrectly, and
    comparing stats in that state would just produce noise.
    """
    tolerances = tolerances or DEFAULT_TOLERANCES

    if SCORE_MUST_MATCH and not scores_agree(flashscore, fonbet):
        return []

    discrepancies = []
    for stat_name, tolerance in tolerances.items():
        fs_value = flashscore.stats.get(stat_name)
        fb_value = fonbet.stats.get(stat_name)
        if fs_value is None or fb_value is None:
            continue

        fs_home, fs_away = fs_value
        fb_home, fb_away = fb_value
        if abs(fs_home - fb_home) > tolerance or abs(fs_away - fb_away) > tolerance:
            discrepancies.append(
                Discrepancy(
                    pair=pair,
                    stat_name=stat_name,
                    flashscore_value=fs_value,
                    fonbet_value=fb_value,
                )
            )
    return discrepancies
