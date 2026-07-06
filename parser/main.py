"""Poll flashscore.com and fon.bet for live football matches, compare their
live stats, and send a Telegram alert whenever they disagree beyond
tolerance.

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
from scrapers.fonbet import FonbetScraper
from telegram_notifier import ConsoleNotifier, TelegramNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("parser")


async def _bounded(sem: asyncio.Semaphore, coro):
    async with sem:
        return await coro


async def _fetch_pair_stats(
    browser: Browser,
    fs_scraper: FlashscoreScraper,
    fb_scraper: FonbetScraper,
    pair: MatchedPair,
) -> tuple[MatchedPair, MatchStats, MatchStats] | None:
    context = await browser.new_context()
    page = await context.new_page()
    try:
        fs_stats = await fs_scraper.get_match_stats(page, pair.flashscore)
        fb_stats = await fb_scraper.get_match_stats(page, pair.fonbet)
        return pair, fs_stats, fb_stats
    except Exception:
        logger.exception(
            "Failed to fetch stats for %s vs %s",
            pair.flashscore.home_team,
            pair.flashscore.away_team,
        )
        return None
    finally:
        await context.close()


async def poll_once(browser: Browser, notifier, state: DiscrepancyState) -> None:
    fs_scraper = FlashscoreScraper()
    fb_scraper = FonbetScraper()

    list_context = await browser.new_context()
    list_page = await list_context.new_page()
    try:
        fs_matches = await fs_scraper.list_live_matches(list_page)
        fb_matches = await fb_scraper.list_live_matches(list_page)
    finally:
        await list_context.close()

    logger.info("Live matches: flashscore=%d fonbet=%d", len(fs_matches), len(fb_matches))

    pairs = [
        p
        for p in match_events(fs_matches, fb_matches, config.NAME_MATCH_THRESHOLD)
        if confirmed(p)
    ]
    logger.info("Confirmed pairs: %d", len(pairs))

    sem = asyncio.Semaphore(config.STATS_CONCURRENCY)
    results = await asyncio.gather(
        *(_bounded(sem, _fetch_pair_stats(browser, fs_scraper, fb_scraper, p)) for p in pairs)
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
    notifier = _build_notifier()
    state = DiscrepancyState()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

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
    asyncio.run(run_forever())
