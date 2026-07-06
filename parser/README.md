# flashscore ↔ fon.bet live-stats parser

Polls live football matches on **flashscore.com** and **fon.bet**, pairs up
the same real-world match across both sites, compares their live statistics
(corners, cards, shots, possession, dangerous attacks), and sends a
**Telegram alert** whenever the two disagree beyond a tolerance.

## ⚠️ Important caveat

This code was written and unit-tested in a sandboxed environment whose
network policy blocks outbound access to both `flashscore.com` and
`fon.bet` (confirmed via the agent proxy — a deliberate policy denial, not
a bug). That means:

- The **matching, comparison, and alerting logic** (`matching.py`,
  `comparator.py`, `pairing.py`) is fully implemented and unit-tested
  (`pytest tests/`, `python demo.py` — both run with zero network access
  and pass).
- The **scrapers** (`scrapers/flashscore.py`, `scrapers/fonbet.py`) are a
  best-effort implementation based on each site's known markup
  conventions, but their CSS selectors have **not been verified against
  the live sites** and will likely need small adjustments. Both sites also
  redesign their frontends periodically. See the docstring at the top of
  each scraper file for exactly what to check/update, and run once with
  `HEADLESS=false` from a network that can reach both sites to confirm.
- Also check each site's Terms of Service before running this
  continuously — automated scraping may be restricted.

## Architecture

```
main.py           orchestration loop (poll -> match -> compare -> notify)
pairing.py        cross-source pair confirmation (score/minute) + alert dedupe
matching.py       team-name matching across Latin (flashscore) / Cyrillic (fon.bet)
comparator.py     tolerance-based stat diffing
models.py         MatchRef / MatchStats / MatchedPair / Discrepancy dataclasses
telegram_notifier.py   Telegram Bot API sender (+ console fallback for dry runs)
scrapers/
  base.py         shared text-based stat-row parsing + canonical stat label table
  flashscore.py   Playwright scraper for flashscore.com
  fonbet.py       Playwright scraper for fon.bet
demo.py           runs the full pipeline on canned sample data, no network needed
tests/            pytest unit tests for matching/comparator/pairing
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
cd parser
pip install -r requirements.txt
python -m playwright install chromium   # skip if already installed on the host
cp .env.example .env
# edit .env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

Get a Telegram bot token from [@BotFather](https://t.me/BotFather), and
your chat id by messaging the bot then visiting
`https://api.telegram.org/bot<token>/getUpdates`. Without these two env
vars set, alerts print to the console instead (useful for testing).

## Run

```bash
python demo.py     # sanity-check the pipeline logic, no network/browser needed
pytest tests/       # unit tests
python main.py      # the real thing: polls both sites every POLL_INTERVAL_SECONDS
```

## Config (`.env` / env vars, see `config.py`)

| Variable                | Default | Meaning |
|--------------------------|---------|---------|
| `TELEGRAM_BOT_TOKEN`     | —       | Telegram bot token; empty = console-only alerts |
| `TELEGRAM_CHAT_ID`       | —       | Telegram chat/user id to send alerts to |
| `POLL_INTERVAL_SECONDS`  | `60`    | Seconds between poll cycles |
| `NAME_MATCH_THRESHOLD`   | `0.55`  | Minimum team-name similarity to consider a candidate pair |
| `HEADLESS`               | `true`  | Run Chromium headless; set `false` to debug selectors visually |
| `STATS_CONCURRENCY`      | `4`     | Max concurrent per-match stats page fetches |

Per-stat tolerances (how big a difference counts as a "discrepancy") live
in `comparator.DEFAULT_TOLERANCES`.
