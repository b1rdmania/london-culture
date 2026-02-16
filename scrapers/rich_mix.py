import re
from datetime import date, datetime

from .base import BaseScraper, Event


class RichMixScraper(BaseScraper):
    name = "Rich Mix"
    base_url = "https://richmix.org.uk"

    def scrape(self) -> list[Event]:
        events = []
        try:
            soup = self._get(f"{self.base_url}/whats-on/this-week")
            events.extend(self._parse_page(soup))

            # Also get next week
            soup2 = self._get(f"{self.base_url}/whats-on/next-week")
            events.extend(self._parse_page(soup2))
        except Exception as e:
            self.logger.error(f"Rich Mix scrape failed: {e}")
        return events

    def _parse_page(self, soup) -> list[Event]:
        events = []
        for tease in soup.select("div.tease"):
            title_el = tease.select_one("h3 a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")

            # Category
            cat_el = tease.select_one("span.category")
            category = cat_el.get_text(strip=True) if cat_el else ""

            # Skip music, cinema, performance, and family events
            cat_lower = category.lower()
            if cat_lower in ("families", "kids", "children", "music", "cinema", "live events", "gigs"):
                continue

            # Date
            date_el = tease.select_one("span.date")
            date_text = date_el.get_text(strip=True) if date_el else ""
            event_date = self._parse_date(date_text) if date_text else None

            # Free?
            is_free = bool(tease.select_one("span.flag"))

            events.append(Event(
                title=title,
                venue=self.name,
                url=href,
                start_date=event_date,
                category=category,
                is_free=is_free,
                area="Shoreditch",
            ))
        return events

    def _parse_date(self, text: str) -> date | None:
        """Parse dates like 'SUN 25 JAN', 'FRI 14 FEB', 'SAT 15 FEB'."""
        text = text.strip().upper()
        m = re.match(r"[A-Z]{3}\s+(\d+)\s+([A-Z]{3})", text)
        if m:
            day = int(m.group(1))
            month_str = m.group(2)
            months = {
                "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
                "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
            }
            month = months.get(month_str)
            if month:
                year = date.today().year
                try:
                    d = date(year, month, day)
                    # If date is far in the past, it's probably next year
                    if d < date.today() - __import__("datetime").timedelta(days=60):
                        d = date(year + 1, month, day)
                    return d
                except ValueError:
                    pass
        return None
