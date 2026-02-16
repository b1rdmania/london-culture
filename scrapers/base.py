from dataclasses import dataclass
from datetime import date
from typing import Optional
import logging
import time

import requests
from bs4 import BeautifulSoup


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

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "LondonCulture/1.0 (personal event aggregator)"
        })

    def scrape(self) -> list[Event]:
        raise NotImplementedError

    def _get(self, url: str) -> BeautifulSoup:
        time.sleep(1)
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
