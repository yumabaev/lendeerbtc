import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matching import normalize, transliterate, match_events
from models import MatchRef


def test_transliterate_basic():
    assert transliterate("реал") == "real"
    assert transliterate("Барселона") == "barselona"


def test_normalize_strips_club_suffixes_and_case():
    assert normalize("Manchester United FC") == normalize("manchester utd")


def test_normalize_transliterates_cyrillic_close_to_latin_form():
    # not identical (transliteration != real translation) but should be close
    ru = normalize("Спартак")
    assert ru == "spartak"


def _ref(source, mid, home, away, minute="10", score=(0, 0)):
    return MatchRef(
        source=source, match_id=mid, url="http://x", home_team=home, away_team=away,
        minute=minute, score_home=score[0], score_away=score[1],
    )


def test_match_events_pairs_aliased_teams():
    fs = [_ref("flashscore", "fs1", "Real Madrid", "Barcelona")]
    fb = [_ref("fonbet", "fb1", "Реал Мадрид", "Барселона")]

    pairs = match_events(fs, fb)

    assert len(pairs) == 1
    assert pairs[0].flashscore.match_id == "fs1"
    assert pairs[0].fonbet.match_id == "fb1"
    assert pairs[0].confidence == 1.0


def test_match_events_does_not_pair_unrelated_teams():
    fs = [_ref("flashscore", "fs1", "Real Madrid", "Barcelona")]
    fb = [_ref("fonbet", "fb1", "Ливерпуль", "Челси")]

    pairs = match_events(fs, fb)

    assert pairs == []


def test_match_events_is_one_to_one():
    fs = [
        _ref("flashscore", "fs1", "Real Madrid", "Barcelona"),
        _ref("flashscore", "fs2", "Real Madrid", "Barcelona"),
    ]
    fb = [_ref("fonbet", "fb1", "Реал Мадрид", "Барселона")]

    pairs = match_events(fs, fb)

    assert len(pairs) == 1
