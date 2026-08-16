from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import logging
import time

import requests
from bs4 import BeautifulSoup

# A real browser UA. The old "LondonCulture/1.0" UA got 403/405 from
# Eventbrite and Rich Mix on GitHub Actions' datacenter IPs.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class BlockedError(Exception):
    """Site refused us (403/405/429) — try the browser fallback."""


@dataclass
class Event:
    title: str
    venue: str
    url: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    time: str = ""  # e.g. "7pm", "19:00 – 22:00"
    description: str = ""
    category: str = ""
    is_free: bool = False
    area: str = ""  # e.g. "Dalston", "Shoreditch", "South Kensington"
    source: str = ""  # scraper name (venue may differ, e.g. Eventbrite/Luma)
    postcode: str = ""  # outward code if known, e.g. "E8", "N1", "SE1"
    image: str = ""  # event image URL if the source gives one

    @property
    def date_display(self) -> str:
        parts = []
        if self.start_date and self.end_date and self.start_date != self.end_date:
            parts.append(f"{self.start_date.strftime('%-d %b')} – {self.end_date.strftime('%-d %b %Y')}")
        elif self.start_date:
            parts.append(self.start_date.strftime("%a %-d %b"))
        elif self.end_date:
            parts.append(f"Until {self.end_date.strftime('%-d %b')}")
        if self.time:
            parts.append(self.time)
        return ", ".join(parts)


class BaseScraper:
    name: str = ""
    base_url: str = ""
    # Set by the runner when a Playwright page is available. Used as a
    # fallback when a site blocks plain requests.
    page = None

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        })

    def scrape(self) -> list[Event]:
        raise NotImplementedError

    def _get_text(self, url: str, wait_ms: int = 0) -> str:
        """Fetch a URL. Plain requests first; on 403/405/429 fall back to
        the shared Playwright page if the runner gave us one."""
        time.sleep(1)
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code in (403, 405, 429):
                raise BlockedError(f"{resp.status_code} for {url}")
            resp.raise_for_status()
            return resp.text
        except BlockedError as e:
            if self.page is None:
                raise
            self.logger.warning(f"{e} — retrying via browser")
            return self._browser_text(url, wait_ms)

    def _browser_text(self, url: str, wait_ms: int = 0) -> str:
        self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        if wait_ms:
            self.page.wait_for_timeout(wait_ms)
        return self.page.content()

    def _get(self, url: str) -> BeautifulSoup:
        return BeautifulSoup(self._get_text(url), "html.parser")
