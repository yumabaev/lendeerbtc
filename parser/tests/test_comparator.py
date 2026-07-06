import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comparator import compare
from models import MatchedPair, MatchRef, MatchStats


def _ref(source, mid, score=(1, 0)):
    return MatchRef(
        source=source, match_id=mid, url="http://x", home_team="A", away_team="B",
        minute="50", score_home=score[0], score_away=score[1],
    )


def test_compare_flags_stat_beyond_tolerance():
    fs_ref, fb_ref = _ref("flashscore", "fs1"), _ref("fonbet", "fb1")
    pair = MatchedPair(flashscore=fs_ref, fonbet=fb_ref, confidence=1.0)

    fs_stats = MatchStats(ref=fs_ref, stats={"corners": (5.0, 2.0)})
    fb_stats = MatchStats(ref=fb_ref, stats={"corners": (5.0, 5.0)})

    discs = compare(pair, fs_stats, fb_stats)

    assert len(discs) == 1
    assert discs[0].stat_name == "corners"


def test_compare_ignores_within_tolerance():
    fs_ref, fb_ref = _ref("flashscore", "fs1"), _ref("fonbet", "fb1")
    pair = MatchedPair(flashscore=fs_ref, fonbet=fb_ref, confidence=1.0)

    fs_stats = MatchStats(ref=fs_ref, stats={"corners": (5.0, 2.0)})
    fb_stats = MatchStats(ref=fb_ref, stats={"corners": (6.0, 2.0)})  # tolerance is 1

    discs = compare(pair, fs_stats, fb_stats)

    assert discs == []


def test_compare_skips_when_scores_disagree():
    fs_ref = _ref("flashscore", "fs1", score=(1, 0))
    fb_ref = _ref("fonbet", "fb1", score=(1, 1))  # disagreeing score -> likely bad pairing
    pair = MatchedPair(flashscore=fs_ref, fonbet=fb_ref, confidence=1.0)

    fs_stats = MatchStats(ref=fs_ref, stats={"corners": (5.0, 2.0)})
    fb_stats = MatchStats(ref=fb_ref, stats={"corners": (9.0, 9.0)})

    discs = compare(pair, fs_stats, fb_stats)

    assert discs == []


def test_compare_ignores_stats_missing_on_one_side():
    fs_ref, fb_ref = _ref("flashscore", "fs1"), _ref("fonbet", "fb1")
    pair = MatchedPair(flashscore=fs_ref, fonbet=fb_ref, confidence=1.0)

    fs_stats = MatchStats(ref=fs_ref, stats={"corners": (5.0, 2.0)})
    fb_stats = MatchStats(ref=fb_ref, stats={})  # scraper couldn't find corners on this side

    discs = compare(pair, fs_stats, fb_stats)

    assert discs == []
