from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Flashscore data comes from the "FlashScore" API on RapidAPI instead of
# scraping flashscore.com directly - see scrapers/flashscore.py.
FLASHSCORE_API_KEY = os.getenv("FLASHSCORE_API_KEY", "")
FLASHSCORE_API_HOST = os.getenv("FLASHSCORE_API_HOST", "flashscore4.p.rapidapi.com")
FLASHSCORE_SPORT_ID = os.getenv("FLASHSCORE_SPORT_ID", "1")  # 1 = football
FLASHSCORE_TIMEZONE = os.getenv("FLASHSCORE_TIMEZONE", "Europe/Berlin")

POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "60"))
NAME_MATCH_THRESHOLD = float(os.getenv("NAME_MATCH_THRESHOLD", "0.55"))
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"

STATS_CONCURRENCY = int(os.getenv("STATS_CONCURRENCY", "4"))
