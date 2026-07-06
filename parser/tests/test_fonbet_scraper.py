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

from scrapers.fonbet import LIVE_ROW_SELECTOR, _corners_from_list_row, _corners_from_scoreboard

# Trimmed from two real devtools inspections of a fon.bet match page's
# scoreboard widget. Hash suffixes (--WCEcc etc.) are exactly as observed.
# Includes the "1 тайм" (half-time score) column as a sibling of the
# corners column, both with their own caption/column_t1/column_t2 children,
# to prove the parser reads the *corners* column's own values and doesn't
# accidentally pick up the half-time score's.
SCOREBOARD_HTML = """
<div class="scoreboard--LBSua">
  <div class="scoreboard_table--Tx2YX">
    <div class="column--fgNW_ _active--jPFnC _bold--Aw_dH scoreboard_table_team--BWPZ4">A</div>
    <div class="column--fgNW_ _active--jPFnC _bold--Aw_dH">B</div>
    <div class="column--fgNW_ _separator--jZ9hO">
      <div class="column__caption--j1pIK">1 тайм</div>
      <div class="column_t1--WCEcc">2</div>
      <div class="column_t2--rn4_E">1</div>
    </div>
    <div class="column--fgNW_">C</div>
    <div class="column--fgNW_ _separator--jZ9hO">
      <div class="column__caption--j1pIK">
        <span class="hide svg-resource--QrfQ8 scoreboard_table_icon--P6Ebq _corners--C0HIK"
              resource-name="mcCorner" resource-context="false"></span>
      </div>
      <div class="column_t1--WCEcc">0</div>
      <div class="column_t2--rn4_E">6</div>
    </div>
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
    assert result == (0.0, 6.0)


def test_corners_from_scoreboard_returns_none_without_icon():
    result = asyncio.run(_corners_for_html("<div>no corners here</div>"))
    assert result is None


# Trimmed from a real devtools inspection of the live-football list page
# (fon.bet/live/football) - a match row showing its "угловые" sub-event
# inline, without needing to open the match page at all.
LIST_ROW_HTML = """
<div class="sport-base-event-wrap--WmtIb">
  <div class="sport-base-event--W4qkO _compact--eaFtY">
    <div></div>
    <div></div>
    <div class="sport-base-event__main--FHhdx" style="padding-left: 18px;">
      <div class="sport-base-event__main_caption--JLR1n _clickable--RtjIi _columns--QHpty">
        <div class="table-component-text--Tjj3g sport-sub-event-name--KyVGC _compact--UxlCb _clickable--VS1j1">
          угловые
        </div>
        <div class="sport-base-event__main_caption_slider--upqVQ"></div>
        <span class="event-block-score--QKiav">0:8</span>
        <div class="event-block-comment--Xbf4j">
          <span>(0-6)</span>
        </div>
      </div>
    </div>
  </div>
</div>
"""

LIST_ROW_HTML_NO_CORNERS_SUBEVENT = """
<div class="sport-base-event-wrap--WmtIb">
  <div class="sport-base-event__main_caption--JLR1n">
    <div class="sport-sub-event-name--KyVGC">жёлтые карты</div>
    <span class="event-block-score--QKiav">1:0</span>
  </div>
</div>
"""


async def _corners_from_list_row_for_html(html: str):
    async with async_playwright() as pw:
        browser = await _launch(pw)
        try:
            page = await browser.new_page()
            await page.set_content(html)
            row = page.locator(LIVE_ROW_SELECTOR).first
            return await _corners_from_list_row(row)
        finally:
            await browser.close()


def test_corners_from_list_row_reads_inline_subevent():
    result = asyncio.run(_corners_from_list_row_for_html(LIST_ROW_HTML))
    assert result == (0.0, 8.0)


def test_corners_from_list_row_returns_none_when_no_corners_subevent():
    result = asyncio.run(_corners_from_list_row_for_html(LIST_ROW_HTML_NO_CORNERS_SUBEVENT))
    assert result is None
