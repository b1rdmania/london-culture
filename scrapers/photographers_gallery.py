import re
from datetime import date, datetime

from .base import BaseScraper, Event


# Only these categories — skip Exhibitions, Youth Programme, etc.
INCLUDE_TYPES = {"Talks & Events", "Workshops & Courses", "Bookshop Event", "Tours"}


class PhotographersGalleryScraper(BaseScraper):
    name = "Photographers' Gallery"
    base_url = "https://thephotographersgallery.org.uk"

    def scrape(self) -> list[Event]:
        events = []
        try:
            soup = self._get(f"{self.base_url}/whats-on")
            events.extend(self._parse_page(soup))
        except Exception as e:
            self.logger.error(f"Photographers' Gallery scrape failed: {e}")
        return events

    def _parse_page(self, soup) -> list[Event]:
        events = []
        for card in soup.select("article.o-event"):
            # Category
            type_el = card.select_one("span.o-teaser__post-type")
            category = type_el.get_text(strip=True) if type_el else ""
            if category and category not in INCLUDE_TYPES:
                continue

            # Title
            title_el = card.select_one("a.o-teaser__link")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if not title or not href:
                continue

            # Date
            date_el = card.select_one("p.o-teaser__date")
            date_text = date_el.get_text(strip=True) if date_el else ""
            start_date, time_str = self._parse_date(date_text)

            # Skip past events
            if start_date and start_date < date.today():
                continue

            # Description
            desc_el = card.select_one("p.o-teaser__body-text")
            description = desc_el.get_text(strip=True)[:200] if desc_el else ""

            url = f"{self.base_url}{href}" if not href.startswith("http") else href

            events.append(Event(
                title=title,
                venue=self.name,
                url=url,
                start_date=start_date,
                time=time_str,
                description=description,
                category=category,
                area="Soho",
            ))
        return events

    def _parse_date(self, text: str) -> tuple[date | None, str]:
        """Parse dates like '6:30pm, Thu 19 Feb 2026' or '06 Feb 2026 - 19 Apr 2026'."""
        text = text.strip()

        # Single event with time: "6:30pm, Thu 19 Feb 2026"
        m = re.match(r"(\d+:\d+[ap]m),\s+\w+\s+(\d+)\s+(\w+)\s+(\d{4})", text)
        if m:
            time_str = m.group(1)
            day, month_str, year = int(m.group(2)), m.group(3), int(m.group(4))
            d = self._make_date(day, month_str, year)
            return d, time_str

        # Date range: "06 Feb 2026 - 19 Apr 2026" — use start date
        m = re.match(r"(\d+)\s+(\w+)\s+(\d{4})\s*-", text)
        if m:
            day, month_str, year = int(m.group(1)), m.group(2), int(m.group(3))
            return self._make_date(day, month_str, year), ""

        # Simple date: "19 Feb 2026"
        m = re.match(r"(\d+)\s+(\w+)\s+(\d{4})", text)
        if m:
            day, month_str, year = int(m.group(1)), m.group(2), int(m.group(3))
            return self._make_date(day, month_str, year), ""

        return None, ""

    def _make_date(self, day: int, month_str: str, year: int) -> date | None:
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        month = months.get(month_str[:3].lower())
        if not month:
            return None
        try:
            return date(year, month, day)
        except ValueError:
            return None
