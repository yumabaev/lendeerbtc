"""Exercises the confirmed corners selector against static HTML that
mirrors the real devtools structure it was built from (see the
scrapers/fonbet.py module docstring) - runs a real headless Chromium via
Playwright, but needs no network access at all (page.set_content)."""

import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.fonbet import _corners_from_scoreboard

# Trimmed from a real devtools inspection of a fon.bet match page's
# scoreboard widget. Hash suffixes (--WCEcc etc.) are exactly as observed -
# _corners_from_scoreboard must not depend on them, only on the
# resource-name="mcCorner" marker and the column_t1/column_t2 prefixes.
SCOREBOARD_HTML = """
<div class="scoreboard--LBSua">
  <div class="scoreboard_table--Tx2YX">
    <div class="column--fgNW_ _active--jPFnC _bold--Aw_dH scoreboard_table_team--BWPZ4">A</div>
    <div class="column--fgNW_ _active--jPFnC _bold--Aw_dH">B</div>
    <div class="column--fgNW_ _separator--jZ9hO">C</div>
    <div class="column--fgNW_ _separator--jZ9hO">
      <div class="column__caption--j1piK">
        <span class="hide svg-resource--QrfQ8 scoreboard_table_icon--P6Ebq _corners--C0HIK"
              resource-name="mcCorner" resource-context="false"></span>
      </div>
    </div>
    <div class="column_t1--WCEcc">0</div>
    <div class="column_t2--rn4_E">3</div>
  </div>
</div>
"""

# This sandbox pins a Playwright pip version newer than the pre-downloaded
# browser revision at /opt/pw-browsers; production environments won't have
# this mismatch, so only fall back to the pinned path if the default launch
# fails.
_PINNED_CHROMIUM = "/opt/pw-browsers/chromium"


async def _launch(pw):
    try:
        return await pw.chromium.launch()
    except Exception:
        if os.path.exists(_PINNED_CHROMIUM):
            return await pw.chromium.launch(executable_path=_PINNED_CHROMIUM)
        raise


async def _corners_for_html(html: str):
    async with async_playwright() as pw:
        browser = await _launch(pw)
        try:
            page = await browser.new_page()
            await page.set_content(html)
            return await _corners_from_scoreboard(page)
        finally:
            await browser.close()


def test_corners_from_scoreboard_reads_confirmed_structure():
    result = asyncio.run(_corners_for_html(SCOREBOARD_HTML))
    assert result == (0.0, 3.0)


def test_corners_from_scoreboard_returns_none_without_icon():
    result = asyncio.run(_corners_for_html("<div>no corners here</div>"))
    assert result is None
