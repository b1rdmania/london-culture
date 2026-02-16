import re
from datetime import date, datetime

from .base import BaseScraper, Event


# Words in title that indicate film screenings (not social events)
FILM_WORDS = ["film programme", "screening", "on 35mm", "on 16mm"]


class ICAScraper(BaseScraper):
    name = "ICA"
    base_url = "https://www.ica.art"
    requires_browser = True

    def scrape(self, page=None) -> list[Event]:
        if page is None:
            self.logger.warning("No browser available, skipping ICA")
            return []

        events = []
        try:
            from bs4 import BeautifulSoup

            page.goto(f"{self.base_url}/talks", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(5000)
            soup = BeautifulSoup(page.content(), "html.parser")

            for item in soup.select("div.item.talks"):
                link = item.find("a", href=True)
                if not link:
                    continue

                href = link.get("href", "")
                if not href.startswith("/talks/") or href in ("/talks/tomorrow", "/talks/next-7-days", "/talks/today", "/talks/2026", "/talks/2025"):
                    continue

                # Title from .title div — may have <br> between prefix and title
                title_el = item.select_one(".title")
                if title_el:
                    # Get text parts split by <br> (prefix like WORKSHOP, then actual title)
                    parts = []
                    for child in title_el.children:
                        if hasattr(child, "name") and child.name == "br":
                            continue
                        text = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
                        if text:
                            parts.append(text.rstrip(":"))
                    title = " — ".join(parts) if len(parts) > 1 else (parts[0] if parts else "")
                else:
                    info_el = item.select_one(".item-info")
                    title = info_el.get_text(strip=True) if info_el else ""
                if not title:
                    continue

                # Skip film screenings
                title_lower = title.lower()
                if any(w in title_lower for w in FILM_WORDS):
                    continue

                # Date from .date
                date_el = item.select_one(".date")
                date_text = date_el.get_text(strip=True) if date_el else ""
                start_date, is_range = self._parse_date(date_text)

                # Skip ongoing programmes (multi-month ranges) — we want single events
                if is_range:
                    continue

                # Skip past events
                if start_date and start_date < date.today():
                    continue

                # Description from .description
                desc_el = item.select_one(".description")
                description = desc_el.get_text(strip=True)[:200] if desc_el else ""

                url = f"{self.base_url}{href}" if not href.startswith("http") else href

                events.append(Event(
                    title=title,
                    venue=self.name,
                    url=url,
                    start_date=start_date,
                    description=description,
                    category="Talks & events",
                    area="The Mall",
                ))

        except Exception as e:
            self.logger.error(f"ICA scrape failed: {e}")
        return events

    def _parse_date(self, text: str) -> tuple[date | None, bool]:
        """Parse ICA date strings. Returns (date, is_range)."""
        text = text.strip()

        # "Tue, 17 February" or "Sun, 22 February" — single event
        m = re.match(r"[A-Za-z]+,\s+(\d+)\s+([A-Za-z]+)$", text)
        if m:
            return self._make_date(int(m.group(1)), m.group(2)), False

        # "18 – 29 March 2026" (short range within same month)
        m = re.match(r"(\d+)\s*[–-]\s*\d+\s+([A-Za-z]+)", text)
        if m:
            return self._make_date(int(m.group(1)), m.group(2)), False

        # "4 February – 3 June 2026" or "30 April 2025 – 30 April 2026" (long range — ongoing programme)
        m = re.match(r"(\d+)\s+([A-Za-z]+)(?:\s+\d{4})?\s*[–-]", text)
        if m:
            return self._make_date(int(m.group(1)), m.group(2)), True

        return None, False

    def _make_date(self, day: int, month_str: str) -> date | None:
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }
        month = months.get(month_str.lower())
        if not month:
            return None
        year = date.today().year
        try:
            d = date(year, month, day)
            if d < date.today() - __import__("datetime").timedelta(days=60):
                d = date(year + 1, month, day)
            return d
        except ValueError:
            return None
