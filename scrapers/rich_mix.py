import re
from datetime import date

from .base import BaseScraper, Event

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


class RichMixScraper(BaseScraper):
    """Rich Mix redesigned (2026): /whats-on/ lists cinema + events as
    `.c-card--event` cards. Cinema cards link to /cinema/, events to /events/."""
    name = "Rich Mix"
    base_url = "https://richmix.org.uk"

    def scrape(self) -> list[Event]:
        events = []
        try:
            soup = self._get(f"{self.base_url}/whats-on/")
            events.extend(self._parse_page(soup))
        except Exception as e:
            self.logger.error(f"Rich Mix scrape failed: {e}")
        return events

    def _parse_page(self, soup) -> list[Event]:
        events = []
        seen = set()
        for card in soup.select(".c-card--event"):
            title_el = card.select_one(".c-card__title a")
            if not title_el:
                continue
            href = title_el.get("href", "")
            if "/cinema/" in href or href in seen:
                continue
            seen.add(href)
            title = title_el.get_text(strip=True)

            time_el = card.select_one("time.c-card__datetime")
            date_text = time_el.get_text(" ", strip=True) if time_el else ""
            if date_text.upper().startswith("FROM"):
                # Ongoing run — not a single evening out
                continue
            start = self._parse_date(date_text)

            tags = [t.get_text(strip=True) for t in card.select(".c-card__tags .c-tag")]
            tag_text = " ".join(tags).lower()
            if any(w in tag_text for w in ("family", "kids", "children")):
                continue
            is_free = "free" in tag_text

            events.append(Event(
                title=title,
                venue=self.name,
                url=href,
                start_date=start,
                category=self._guess_category(title, href),
                is_free=is_free,
                area="Shoreditch",
                source=self.name,
            ))
        return events

    @staticmethod
    def _guess_category(title: str, href: str) -> str:
        t = title.lower()
        if any(w in t for w in ("workshop", "class", "life drawing")):
            return "Workshops"
        if any(w in t for w in ("talk", "conversation", "panel", "in conversation")):
            return "Talks"
        if any(w in t for w in ("poetry", "spoken word", "book", "reading")):
            return "Writing"
        if any(w in t for w in ("comedy", "quiz", "social", "night")):
            return "Social"
        return "Other"

    def _parse_date(self, text: str) -> date | None:
        text = text.strip().upper()
        if not text:
            return None
        m = re.search(r"(\d{1,2})\s+([A-Z]{3,4})", text)
        if not m:
            return None
        month = MONTHS.get(m.group(2))
        if not month:
            return None
        day = int(m.group(1))
        today = date.today()
        try:
            d = date(today.year, month, day)
            if d < today:
                d = date(today.year + 1, month, day)
            return d
        except ValueError:
            return None
