"""Runs the matching + comparison + notification pipeline on canned sample
data, without touching the network or a browser.

Useful for verifying the pipeline's logic (name matching across
Latin/Cyrillic scripts, score-based pairing confirmation, tolerance-based
stat comparison, alert formatting) in environments where flashscore.com /
fon.bet aren't reachable.

Run:
    python demo.py
"""

from __future__ import annotations

from comparator import compare
from matching import match_events
from pairing import confirmed
from models import MatchRef, MatchStats
from telegram_notifier import ConsoleNotifier

FLASHSCORE_LIVE = [
    MatchRef(
        source="flashscore", match_id="fs1", url="https://www.flashscore.com/match/fs1/",
        home_team="Real Madrid", away_team="Barcelona",
        minute="63'", score_home=2, score_away=1,
    ),
    MatchRef(
        source="flashscore", match_id="fs2", url="https://www.flashscore.com/match/fs2/",
        home_team="Manchester City", away_team="Liverpool",
        minute="40'", score_home=0, score_away=0,
    ),
]

FONBET_LIVE = [
    MatchRef(
        source="fonbet", match_id="fb1", url="https://fon.bet/live/fb1",
        home_team="Реал Мадрид", away_team="Барселона",
        minute="64", score_home=2, score_away=1,
    ),
    MatchRef(
        source="fonbet", match_id="fb2", url="https://fon.bet/live/fb2",
        home_team="Манчестер Сити", away_team="Ливерпуль",
        minute="41", score_home=0, score_away=0,
    ),
]

FLASHSCORE_STATS = {
    "fs1": {"corners": (6.0, 3.0), "yellow_cards": (2.0, 1.0), "possession": (58.0, 42.0)},
    "fs2": {"corners": (4.0, 2.0), "yellow_cards": (0.0, 0.0), "possession": (50.0, 50.0)},
}

FONBET_STATS = {
    "fb1": {"corners": (6.0, 3.0), "yellow_cards": (4.0, 1.0), "possession": (58.0, 42.0)},
    "fb2": {"corners": (4.0, 2.0), "yellow_cards": (0.0, 0.0), "possession": (50.0, 50.0)},
}


def main() -> None:
    pairs = [p for p in match_events(FLASHSCORE_LIVE, FONBET_LIVE) if confirmed(p)]
    print(f"Matched {len(pairs)} pair(s) out of {len(FLASHSCORE_LIVE)} live matches\n")

    notifier = ConsoleNotifier()
    for pair in pairs:
        fs_stats = MatchStats(ref=pair.flashscore, stats=FLASHSCORE_STATS[pair.flashscore.match_id])
        fb_stats = MatchStats(ref=pair.fonbet, stats=FONBET_STATS[pair.fonbet.match_id])
        discrepancies = compare(pair, fs_stats, fb_stats)
        print(
            f"{pair.flashscore.home_team} vs {pair.flashscore.away_team} "
            f"(confidence={pair.confidence:.2f}): {len(discrepancies)} discrepancy(ies)"
        )
        notifier.send_discrepancies(discrepancies)


if __name__ == "__main__":
    main()
