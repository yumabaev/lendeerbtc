import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comparator import compare
from models import Discrepancy, MatchedPair, MatchRef
from pairing import DiscrepancyState, confirmed


def _ref(source, mid, minute, score):
    return MatchRef(
        source=source, match_id=mid, url="http://x", home_team="A", away_team="B",
        minute=minute, score_home=score[0], score_away=score[1],
    )


def test_confirmed_true_when_score_and_minute_agree():
    pair = MatchedPair(
        flashscore=_ref("flashscore", "fs1", "50'", (1, 0)),
        fonbet=_ref("fonbet", "fb1", "51", (1, 0)),
        confidence=1.0,
    )
    assert confirmed(pair) is True


def test_confirmed_false_when_scores_disagree():
    pair = MatchedPair(
        flashscore=_ref("flashscore", "fs1", "50'", (1, 0)),
        fonbet=_ref("fonbet", "fb1", "51", (2, 0)),
        confidence=1.0,
    )
    assert confirmed(pair) is False


def test_confirmed_false_when_minutes_far_apart():
    pair = MatchedPair(
        flashscore=_ref("flashscore", "fs1", "10'", (0, 0)),
        fonbet=_ref("fonbet", "fb1", "80", (0, 0)),
        confidence=1.0,
    )
    assert confirmed(pair) is False


def _disc(pair, stat_name, fs_value, fb_value):
    return Discrepancy(pair=pair, stat_name=stat_name, flashscore_value=fs_value, fonbet_value=fb_value)


def test_discrepancy_state_dedupes_identical_values():
    pair = MatchedPair(
        flashscore=_ref("flashscore", "fs1", "50'", (1, 0)),
        fonbet=_ref("fonbet", "fb1", "50", (1, 0)),
        confidence=1.0,
    )
    state = DiscrepancyState()
    d1 = _disc(pair, "corners", (5.0, 2.0), (7.0, 2.0))
    d2 = _disc(pair, "corners", (5.0, 2.0), (7.0, 2.0))

    assert state.is_new(d1) is True
    assert state.is_new(d2) is False


def test_discrepancy_state_reports_changed_values_again():
    pair = MatchedPair(
        flashscore=_ref("flashscore", "fs1", "50'", (1, 0)),
        fonbet=_ref("fonbet", "fb1", "50", (1, 0)),
        confidence=1.0,
    )
    state = DiscrepancyState()
    d1 = _disc(pair, "corners", (5.0, 2.0), (7.0, 2.0))
    d2 = _disc(pair, "corners", (6.0, 2.0), (9.0, 2.0))

    assert state.is_new(d1) is True
    assert state.is_new(d2) is True
