from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "60"))
NAME_MATCH_THRESHOLD = float(os.getenv("NAME_MATCH_THRESHOLD", "0.55"))
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"

STATS_CONCURRENCY = int(os.getenv("STATS_CONCURRENCY", "4"))
