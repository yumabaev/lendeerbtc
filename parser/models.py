from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MatchRef:
    """Lightweight reference to a live match found on a live-matches list page."""

    source: str          # "flashscore" | "fonbet"
    match_id: str        # source-specific id (used to build the stats page url)
    url: str
    home_team: str
    away_team: str
    league: str = ""
    minute: str = ""      # raw elapsed-time text, e.g. "63'"
    score_home: int | None = None
    score_away: int | None = None


@dataclass
class MatchStats:
    """Parsed live statistics for one match from one source."""

    ref: MatchRef
    # canonical stat name -> (home_value, away_value)
    stats: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchedPair:
    flashscore: MatchRef
    fonbet: MatchRef
    confidence: float


@dataclass(frozen=True)
class Discrepancy:
    pair: MatchedPair
    stat_name: str
    flashscore_value: tuple[float, float]
    fonbet_value: tuple[float, float]

    def describe(self) -> str:
        home, away = self.pair.flashscore.home_team, self.pair.flashscore.away_team
        fh, fa = self.flashscore_value
        bh, ba = self.fonbet_value
        return (
            f"{home} — {away} [{self.stat_name}]\n"
            f"  Flashscore: {fh:g} : {fa:g}\n"
            f"  Fon.bet:    {bh:g} : {ba:g}"
        )
