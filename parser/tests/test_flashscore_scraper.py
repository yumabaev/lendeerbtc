import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.flashscore import _to_number, parse_live_matches, parse_match_stats

# Trimmed from a real /matches/live response.
LIVE_MATCHES_SAMPLE = [
    {
        "name": "BAHRAIN: Premier League",
        "country_name": "Bahrain",
        "matches": [
            {
                "match_id": "vJPX62Pi",
                "match_status": {
                    "is_started": True,
                    "is_in_progress": True,
                    "is_finished": False,
                    "live_time": "22",
                },
                "home_team": {"team_id": "GYVW06rb", "name": "Al-Hidd"},
                "away_team": {"team_id": "UwXjFqS3", "name": "Bahrain SC"},
                "scores": {"home": 1, "away": 0},
                "odds": {"1": 1.69, "2": 4.54, "X": 3.89},
            }
        ],
    },
    {
        "name": "IRAQ: Stars League",
        "country_name": "Iraq",
        "matches": [
            {
                "match_id": "zqpWiNtI",
                "match_status": {
                    "is_started": True,
                    "is_in_progress": True,
                    "is_finished": False,
                    "live_time": "90+",
                },
                "home_team": {"team_id": "84r5OlNu", "name": "Al Shorta"},
                "away_team": {"team_id": "6ynQ61PT", "name": "Naft Missan"},
                "scores": {"home": 2, "away": 0},
                "odds": {"1": 1.4, "2": 7.84, "X": 4.39},
            }
        ],
    },
]

# Trimmed from a real /matches/match/stats response (duplicate rows kept, as
# the live API actually returns a "summary" section followed by a "detailed"
# section repeating some of the same stats).
MATCH_STATS_SAMPLE = {
    "match": [
        {"name": "Expected goals (xG)", "home_team": 0.55, "away_team": 2.07},
        {"name": "Ball possession", "home_team": "38%", "away_team": "62%"},
        {"name": "Total shots", "home_team": 6, "away_team": 16},
        {"name": "Shots on target", "home_team": 1, "away_team": 6},
        {"name": "Corner kicks", "home_team": 1, "away_team": 7},
        {"name": "Passes", "home_team": "81% (281/346)", "away_team": "91% (518/571)"},
        {"name": "Yellow cards", "home_team": 0, "away_team": 1},
        {"name": "Red cards", "home_team": 2, "away_team": 0},
        # duplicated "detailed" section repeats some rows:
        {"name": "Total shots", "home_team": 6, "away_team": 16},
        {"name": "Shots on target", "home_team": 1, "away_team": 6},
        {"name": "Shots off target", "home_team": 4, "away_team": 5},
        {"name": "Corner kicks", "home_team": 1, "away_team": 7},
    ]
}


def test_to_number_handles_plain_numbers():
    assert _to_number(6) == 6.0
    assert _to_number(0.55) == 0.55


def test_to_number_handles_percentage_strings():
    assert _to_number("38%") == 38.0


def test_to_number_handles_percentage_with_fraction():
    assert _to_number("81% (281/346)") == 81.0


def test_to_number_returns_none_for_unparseable():
    assert _to_number(None) is None
    assert _to_number("n/a") is None


def test_parse_live_matches_extracts_refs():
    matches = parse_live_matches(LIVE_MATCHES_SAMPLE)

    assert len(matches) == 2
    first = matches[0]
    assert first.match_id == "vJPX62Pi"
    assert first.home_team == "Al-Hidd"
    assert first.away_team == "Bahrain SC"
    assert first.league == "BAHRAIN: Premier League"
    assert first.score_home == 1
    assert first.score_away == 0
    assert first.minute == "22"


def test_parse_live_matches_minute_field_survives_non_numeric_stage():
    matches = parse_live_matches(LIVE_MATCHES_SAMPLE)
    second = matches[1]
    assert second.minute == "90+"


def test_parse_match_stats_maps_known_fields():
    stats = parse_match_stats(MATCH_STATS_SAMPLE)

    assert stats["corners"] == (1.0, 7.0)
    assert stats["yellow_cards"] == (0.0, 1.0)
    assert stats["red_cards"] == (2.0, 0.0)
    assert stats["shots_on_target"] == (1.0, 6.0)
    assert stats["shots_off_target"] == (4.0, 5.0)
    assert stats["possession"] == (38.0, 62.0)
    assert stats["total_shots"] == (6.0, 16.0)


def test_parse_match_stats_ignores_unmapped_fields():
    stats = parse_match_stats(MATCH_STATS_SAMPLE)
    assert "passes" not in stats
    assert "expected_goals" not in stats


def test_parse_match_stats_first_occurrence_wins_on_duplicates():
    payload = {
        "match": [
            {"name": "Corner kicks", "home_team": 1, "away_team": 7},
            {"name": "Corner kicks", "home_team": 99, "away_team": 99},
        ]
    }
    stats = parse_match_stats(payload)
    assert stats["corners"] == (1.0, 7.0)
