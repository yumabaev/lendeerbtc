"""Poll flashscore.com and pari.ru for live football matches, compare their
live stats, and send a Telegram alert whenever they disagree beyond
tolerance.

pari.ru is used instead of fon.bet: both share identical frontend markup
(confirmed via devtools), but fon.bet actively blocks automated browser
access with an anti-bot wall while pari.ru does not. See
scrapers/fonbet.py and scrapers/pari.py for details - swap the import
below back to FonbetScraper only if you have a legitimate, authorized way
past fon.bet's bot detection.

Run:
    python main.py

Configuration is read from the environment / .env (see config.py and
.env.example). If TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID aren't set,
discrepancies are printed to the console instead of sent to Telegram.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from playwright.async_api import Browser, async_playwright

import config
from comparator import compare
from matching import match_events
from models import Discrepancy, MatchedPair, MatchStats
from pairing import DiscrepancyState, confirmed
from scrapers.flashscore import FlashscoreScraper
from scrapers.pari import PariScraper
from telegram_notifier import ConsoleNotifier, TelegramNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("parser")


async def _bounded(sem: asyncio.Semaphore, coro):
    async with sem:
        return await coro


async def _fetch_pair_stats(
    fs_scraper: FlashscoreScraper,
    fb_scraper: PariScraper,
    pair: MatchedPair,
) -> tuple[MatchedPair, MatchStats, MatchStats] | None:
    try:
        fs_stats, fb_stats = await asyncio.gather(
            fs_scraper.get_match_stats(pair.flashscore),
            fb_scraper.get_match_stats(pair.fonbet),
        )
        return pair, fs_stats, fb_stats
    except Exception:
        logger.exception(
            "Failed to fetch stats for %s vs %s",
            pair.flashscore.home_team,
            pair.flashscore.away_team,
        )
        return None


async def poll_once(browser: Browser, notifier, state: DiscrepancyState) -> None:
    fs_scraper = FlashscoreScraper()
    fb_scraper = PariScraper(browser)

    fs_matches, fb_matches = await asyncio.gather(
        fs_scraper.list_live_matches(),
        fb_scraper.list_live_matches(),
    )

    logger.info("Live matches: flashscore=%d pari=%d", len(fs_matches), len(fb_matches))

    # Temporary diagnostic - remove once matching is confirmed working
    # against the real sites. Shows exactly what team-name/score/minute
    # extraction is producing, without needing another devtools round trip.
    for m in fs_matches[:8]:
        logger.info("  flashscore sample: %r vs %r | score=%s-%s minute=%r",
                     m.home_team, m.away_team, m.score_home, m.score_away, m.minute)
    for m in fb_matches[:8]:
        logger.info("  pari sample: %r vs %r | score=%s-%s minute=%r",
                     m.home_team, m.away_team, m.score_home, m.score_away, m.minute)

    candidates = match_events(fs_matches, fb_matches, config.NAME_MATCH_THRESHOLD)
    logger.info("Name-matched candidates: %d", len(candidates))
    pairs = [p for p in candidates if confirmed(p)]
    logger.info("Confirmed pairs: %d", len(pairs))

    sem = asyncio.Semaphore(config.STATS_CONCURRENCY)
    results = await asyncio.gather(
        *(_bounded(sem, _fetch_pair_stats(fs_scraper, fb_scraper, p)) for p in pairs)
    )

    all_discrepancies: list[Discrepancy] = []
    for result in results:
        if result is None:
            continue
        pair, fs_stats, fb_stats = result
        discs = compare(pair, fs_stats, fb_stats)
        all_discrepancies.extend(d for d in discs if state.is_new(d))

    if all_discrepancies:
        logger.info("New discrepancies: %d", len(all_discrepancies))
        notifier.send_discrepancies(all_discrepancies)


def _build_notifier():
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        return TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    logger.warning("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set - printing alerts to console instead")
    return ConsoleNotifier()


async def run_forever() -> None:
    if not config.FLASHSCORE_API_KEY:
        logger.warning(
            "FLASHSCORE_API_KEY not set - Flashscore requests will fail (see .env.example)"
        )

    notifier = _build_notifier()
    state = DiscrepancyState()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows' asyncio event loop doesn't support signal handlers -
            # Ctrl+C will raise KeyboardInterrupt instead, caught below.
            pass

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=config.HEADLESS)
        try:
            while not stop.is_set():
                try:
                    await poll_once(browser, notifier, state)
                except Exception:
                    logger.exception("Poll cycle failed")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=config.POLL_INTERVAL_SECONDS)
                except asyncio.TimeoutError:
                    pass
        finally:
            await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        pass
