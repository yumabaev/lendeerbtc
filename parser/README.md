# flashscore ↔ fon.bet live-stats parser

Polls live football matches on **flashscore.com** (via a third-party API)
and **fon.bet** (via browser scraping), pairs up the same real-world match
across both sources, compares their live statistics (corners, cards, shots,
possession), and sends a **Telegram alert** whenever the two disagree
beyond a tolerance.

## ⚠️ Important caveat

This code was written and unit-tested in a sandboxed environment whose
network policy blocks outbound access to `flashscore.com`, `fon.bet`,
`rapidapi.com`, and `flashscore4.p.rapidapi.com` (confirmed via the agent
proxy — a deliberate policy denial, not a bug). That means:

- The **matching, comparison, and alerting logic** (`matching.py`,
  `comparator.py`, `pairing.py`) is fully implemented and unit-tested
  (`pytest tests/`, `python demo.py` — both run with zero network access
  and pass).
- **`scrapers/flashscore.py`** talks to the ["FlashScore" API on
  RapidAPI](https://rapidapi.com/rapidapi-org1-rapidapi-org-default/api/flashscore4)
  instead of scraping flashscore.com directly. Its response schema
  (`/matches/live`, `/matches/match/stats`) was confirmed against real API
  responses and is covered by `tests/test_flashscore_scraper.py`, but the
  live HTTP call itself has **not** been exercised from this environment
  (network policy blocks the API host too) — test it with a real
  `FLASHSCORE_API_KEY` before relying on it.
- **`scrapers/fonbet.py`** is a Playwright scraper: fon.bet has no
  equivalent third-party API for a single bookmaker's live odds/stats.
  **Corners are confirmed** — extracted from the match page's persistent
  scoreboard widget via a real devtools inspection, anchored on the
  semantic `resource-name="mcCorner"` icon attribute rather than hashed CSS
  classes (`_corners_from_scoreboard`, covered by
  `tests/test_fonbet_scraper.py` against real headless Chromium). Match
  discovery (`LIVE_ROW_SELECTOR`) and the other stats (cards, shots,
  possession, via a guessed "Статистика" tab) are **still unverified
  guesses** — see the module docstring for what to check next with
  `HEADLESS=false` from a network that can reach fon.bet.
- Also check each site's/API's Terms of Service before running this
  continuously.

## Architecture

```
main.py           orchestration loop (poll -> match -> compare -> notify)
pairing.py        cross-source pair confirmation (score/minute) + alert dedupe
matching.py       team-name matching across Latin (flashscore) / Cyrillic (fon.bet)
comparator.py     tolerance-based stat diffing
models.py         MatchRef / MatchStats / MatchedPair / Discrepancy dataclasses
telegram_notifier.py   Telegram Bot API sender (+ console fallback for dry runs)
scrapers/
  base.py         shared LiveStatsScraper interface + fon.bet text-row parsing
  flashscore.py   HTTP client for the RapidAPI "FlashScore" API (no browser needed)
  fonbet.py       Playwright scraper for fon.bet (owns its own browser context)
demo.py           runs the full pipeline on canned sample data, no network needed
tests/            pytest unit tests for matching/comparator/pairing/flashscore parsing
```

Why matching is hard: Flashscore shows team names in Latin script
("Real Madrid"), fon.bet shows them in Cyrillic ("Реал Мадрид"), so plain
string similarity doesn't work. `matching.py` combines:

1. A curated alias table (`team_aliases.json`) — most reliable, extend it
   over time from `unmatched_teams.log` (auto-logged when a fon.bet match
   can't be paired).
2. A Cyrillic → Latin transliteration + fuzzy match, for teams not yet in
   the alias table.
3. Live-state corroboration (`pairing.confirmed`): even a good name match
   is discarded if the two sources currently disagree on the score or are
   more than a few minutes apart — this avoids false "discrepancy" alerts
   caused by mis-pairing rather than a genuine stats disagreement.

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium   # skip if already installed on the host
cp .env.example .env
# edit .env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, FLASHSCORE_API_KEY
```

- **Telegram**: get a bot token from [@BotFather](https://t.me/BotFather),
  and your chat id by messaging the bot then visiting
  `https://api.telegram.org/bot<token>/getUpdates`. Without these two env
  vars set, alerts print to the console instead (useful for testing).
- **Flashscore API**: subscribe (a free BASIC tier exists) at
  [rapidapi.com/.../flashscore4](https://rapidapi.com/rapidapi-org1-rapidapi-org-default/api/flashscore4)
  and copy the `X-RapidAPI-Key` into `FLASHSCORE_API_KEY`. Treat this key
  as a secret — anyone with it can spend your subscription quota.

## Run

```bash
python demo.py     # sanity-check the pipeline logic, no network/browser needed
pytest tests/       # unit tests
python main.py      # the real thing: polls both sources every POLL_INTERVAL_SECONDS
```

## Config (`.env` / env vars, see `config.py`)

| Variable                | Default | Meaning |
|--------------------------|---------|---------|
| `TELEGRAM_BOT_TOKEN`     | —       | Telegram bot token; empty = console-only alerts |
| `TELEGRAM_CHAT_ID`       | —       | Telegram chat/user id to send alerts to |
| `FLASHSCORE_API_KEY`     | —       | RapidAPI key for the FlashScore API |
| `FLASHSCORE_API_HOST`    | `flashscore4.p.rapidapi.com` | RapidAPI host header |
| `FLASHSCORE_SPORT_ID`    | `1`     | Sport filter for `/matches/live` (1 = football) |
| `FLASHSCORE_TIMEZONE`    | `Europe/Berlin` | Timezone param for `/matches/live` |
| `POLL_INTERVAL_SECONDS`  | `60`    | Seconds between poll cycles |
| `NAME_MATCH_THRESHOLD`   | `0.55`  | Minimum team-name similarity to consider a candidate pair |
| `HEADLESS`               | `true`  | Run Chromium (fon.bet only) headless; set `false` to debug selectors visually |
| `STATS_CONCURRENCY`      | `4`     | Max concurrent per-match stats fetches |

Per-stat tolerances (how big a difference counts as a "discrepancy") live
in `comparator.DEFAULT_TOLERANCES`. Some stats are also **directional** via
`comparator.STAT_DIRECTIONS` — by default `corners` only alerts when
fon.bet's count is *higher* than Flashscore's (fon.bet overstating/lagging
behind the real match), not the reverse. Other stats flag a difference in
either direction unless given their own entry there.
