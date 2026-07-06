"""Flashscore live football data via the "FlashScore" API on RapidAPI
(https://rapidapi.com/rapidapi-org1-rapidapi-org-default/api/flashscore4),
rather than scraping flashscore.com directly.

Unlike scrapers/fonbet.py, this response schema was confirmed against the
live API (not guessed) — see the endpoints below and STAT_NAME_MAP for the
exact field names observed:

    GET https://flashscore4.p.rapidapi.com/api/flashscore/v2/matches/live
        ?sport_id=1&timezone=Europe%2FBerlin
    GET https://flashscore4.p.rapidapi.com/api/flashscore/v2/matches/match/stats
        ?match_id={id}

Requires FLASHSCORE_API_KEY (see config.py / .env.example) — get one by
subscribing to the API on RapidAPI (a free BASIC tier exists).
"""

from __future__ import annotations

import asyncio
import re

import requests

import config
from models import MatchRef, MatchStats
from scrapers.base import LiveStatsScraper

BASE_URL = "https://{host}/api/flashscore/v2"

# Canonical stat name -> exact "name" field in the /matches/match/stats response.
STAT_NAME_MAP: dict[str, str] = {
    "Corner kicks": "corners",
    "Yellow cards": "yellow_cards",
    "Red cards": "red_cards",
    "Shots on target": "shots_on_target",
    "Shots off target": "shots_off_target",
    "Ball possession": "possession",
    "Total shots": "total_shots",
    "Big chances": "big_chances",
}

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _to_number(value: object) -> float | None:
    """Coerces API values like 6, "38%", or "81% (281/346)" to a float
    (the first number in the string — for percentage-with-fraction fields,
    that's the percentage)."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _NUMBER_RE.search(value)
        if match:
            return float(match.group())
    return None


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": config.FLASHSCORE_API_HOST,
        "x-rapidapi-key": config.FLASHSCORE_API_KEY,
    }


def parse_live_matches(groups: list[dict]) -> list[MatchRef]:
    """Pure transform of the /matches/live response body into MatchRefs."""
    matches: list[MatchRef] = []
    for group in groups:
        league = group.get("name", "")
        for m in group.get("matches", []):
            match_id = m.get("match_id")
            if not match_id:
                continue
            status = m.get("match_status") or {}
            scores = m.get("scores") or {}
            home_team = m.get("home_team") or {}
            away_team = m.get("away_team") or {}
            matches.append(
                MatchRef(
                    source="flashscore",
                    match_id=match_id,
                    url=f"https://www.flashscore.com/match/{match_id}/",
                    home_team=home_team.get("name", ""),
                    away_team=away_team.get("name", ""),
                    league=league,
                    minute=str(status.get("live_time") or ""),
                    score_home=scores.get("home"),
                    score_away=scores.get("away"),
                )
            )
    return matches


def parse_match_stats(payload: dict) -> dict[str, tuple[float, float]]:
    """Pure transform of the /matches/match/stats response body into our
    canonical stat dict. The API repeats some rows (a "summary" section
    followed by a "detailed" section with the same name/values) - the first
    occurrence of each canonical stat wins."""
    stats: dict[str, tuple[float, float]] = {}
    for row in payload.get("match", []):
        canonical = STAT_NAME_MAP.get(row.get("name"))
        if not canonical or canonical in stats:
            continue
        home = _to_number(row.get("home_team"))
        away = _to_number(row.get("away_team"))
        if home is not None and away is not None:
            stats[canonical] = (home, away)
    return stats


class FlashscoreScraper(LiveStatsScraper):
    source_name = "flashscore"

    async def list_live_matches(self) -> list[MatchRef]:
        url = BASE_URL.format(host=config.FLASHSCORE_API_HOST) + "/matches/live"
        params = {"sport_id": config.FLASHSCORE_SPORT_ID, "timezone": config.FLASHSCORE_TIMEZONE}
        resp = await asyncio.to_thread(requests.get, url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        return parse_live_matches(resp.json())

    async def get_match_stats(self, ref: MatchRef) -> MatchStats:
        url = BASE_URL.format(host=config.FLASHSCORE_API_HOST) + "/matches/match/stats"
        resp = await asyncio.to_thread(
            requests.get, url, headers=_headers(), params={"match_id": ref.match_id}, timeout=15
        )
        resp.raise_for_status()
        return MatchStats(ref=ref, stats=parse_match_stats(resp.json()))
