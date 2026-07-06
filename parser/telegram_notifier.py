from __future__ import annotations

import logging

import requests

from models import Discrepancy

logger = logging.getLogger(__name__)

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, timeout: float = 10.0):
        self._url = _API_URL.format(token=bot_token)
        self._chat_id = chat_id
        self._timeout = timeout

    def send_discrepancies(self, discrepancies: list[Discrepancy]) -> None:
        for disc in discrepancies:
            self.send_text("⚠️ Расхождение в live-статистике\n\n" + disc.describe())

    def send_text(self, text: str) -> None:
        try:
            resp = requests.post(
                self._url,
                json={"chat_id": self._chat_id, "text": text},
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to send Telegram notification")


class ConsoleNotifier:
    """Dry-run / no-Telegram-configured fallback — just prints."""

    def send_discrepancies(self, discrepancies: list[Discrepancy]) -> None:
        for disc in discrepancies:
            print("⚠️ DISCREPANCY\n" + disc.describe() + "\n")

    def send_text(self, text: str) -> None:
        print(text)
