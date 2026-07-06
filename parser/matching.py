"""Cross-source match identification.

Flashscore team names are in Latin script; Fon.bet team names are in
Cyrillic. Plain string similarity therefore doesn't work directly, so
matching combines three signals:

1. A manually curated alias table (``team_aliases.json``) — the most
   reliable source, populated over time from ``unmatched_teams.log``.
2. A simple Cyrillic -> Latin transliteration, compared with
   ``difflib`` similarity ratios.
3. Live-state corroboration (elapsed minute + current score), applied
   by the caller once candidate pairs are found, to reject
   look-alike-name mismatches.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from models import MatchedPair, MatchRef

ALIASES_PATH = Path(__file__).parent / "team_aliases.json"
UNMATCHED_LOG_PATH = Path(__file__).parent / "unmatched_teams.log"

_CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_STRIP_WORDS = {
    "fc", "cf", "sc", "afc", "cd", "ac", "club", "united", "utd",
    "sport", "sporting", "de", "do", "u17", "u18", "u19", "u20", "u21",
    "u23", "reserves", "reserve", "ii", "women", "w",
}


def transliterate(text: str) -> str:
    return "".join(_CYRILLIC_TO_LATIN.get(ch, ch) for ch in text.lower())


def normalize(name: str) -> str:
    text = transliterate(name.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = [w for w in text.split() if w and w not in _STRIP_WORDS]
    return " ".join(words)


def _load_aliases() -> dict[str, str]:
    if not ALIASES_PATH.exists():
        return {}
    return json.loads(ALIASES_PATH.read_text(encoding="utf-8"))


def log_unmatched(fonbet_home: str, fonbet_away: str) -> None:
    """Append a Fon.bet pair that couldn't be matched, for manual alias curation."""
    with UNMATCHED_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"{fonbet_home} - {fonbet_away}\n")


@dataclass
class _Aliases:
    table: dict[str, str]

    def resolve(self, name: str) -> str:
        return self.table.get(name.strip().lower(), normalize(name))


def name_similarity(fonbet_name: str, flashscore_name: str, aliases: _Aliases) -> float:
    resolved = aliases.resolve(fonbet_name)
    target = normalize(flashscore_name)
    if not resolved or not target:
        return 0.0
    if resolved == target:
        return 1.0
    return SequenceMatcher(None, resolved, target).ratio()


def pair_similarity(fb: MatchRef, fs: MatchRef, aliases: _Aliases) -> float:
    home_sim = name_similarity(fb.home_team, fs.home_team, aliases)
    away_sim = name_similarity(fb.away_team, fs.away_team, aliases)
    return (home_sim + away_sim) / 2


def match_events(
    flashscore_matches: list[MatchRef],
    fonbet_matches: list[MatchRef],
    name_threshold: float = 0.55,
) -> list[MatchedPair]:
    """Greedy best-first pairing of live matches across the two sources.

    Returns only pairs whose team-name similarity clears ``name_threshold``.
    Callers should additionally corroborate with live score/minute before
    treating a pair as confirmed (see ``main.confirm_pair``).
    """
    aliases = _Aliases(_load_aliases())

    candidates: list[tuple[float, MatchRef, MatchRef]] = []
    for fb in fonbet_matches:
        for fs in flashscore_matches:
            score = pair_similarity(fb, fs, aliases)
            if score >= name_threshold:
                candidates.append((score, fs, fb))

    candidates.sort(key=lambda c: c[0], reverse=True)

    used_fs: set[str] = set()
    used_fb: set[str] = set()
    pairs: list[MatchedPair] = []
    for score, fs, fb in candidates:
        if fs.match_id in used_fs or fb.match_id in used_fb:
            continue
        used_fs.add(fs.match_id)
        used_fb.add(fb.match_id)
        pairs.append(MatchedPair(flashscore=fs, fonbet=fb, confidence=score))

    unmatched_fb = [fb for fb in fonbet_matches if fb.match_id not in used_fb]
    for fb in unmatched_fb:
        log_unmatched(fb.home_team, fb.away_team)

    return pairs
