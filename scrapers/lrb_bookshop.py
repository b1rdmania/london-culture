import re
from datetime import date, datetime

from .base import BaseScraper, Event


class LRBBookshopScraper(BaseScraper):
    name = "London Review Bookshop"
    base_url = "https://www.londonreviewbookshop.co.uk"

    def scrape(self) -> list[Event]:
        events = []
        try:
            soup = self._get(f"{self.base_url}/events")
            seen_urls = set()

            for link in soup.select("a[href*='eventbrite']"):
                href = link.get("href", "")
                if href in seen_urls:
                    continue

                # Only parse the "rich" link that has child elements
                title_el = link.select_one("h2.event-preview--title")
                if not title_el:
                    continue
                seen_urls.add(href)

                title = title_el.get_text(strip=True)

                # Date
                date_el = link.select_one("span.event-preview--date")
                date_text = date_el.get_text(strip=True) if date_el else ""
                start_date, time_str = self._parse_date(date_text)

                # Skip past events
                if start_date and start_date < date.today():
                    continue

                # Price / sold out
                price_el = link.select_one("span.event-preview--price")
                price_text = price_el.get_text(strip=True) if price_el else ""
                is_free = "free" in price_text.lower()

                events.append(Event(
                    title=title,
                    venue=self.name,
                    url=href,
                    start_date=start_date,
                    time=time_str,
                    category="Literary event",
                    is_free=is_free,
                    area="Bloomsbury",
                ))

        except Exception as e:
            self.logger.error(f"LRB Bookshop scrape failed: {e}")
        return events

    def _parse_date(self, text: str) -> tuple[date | None, str]:
        """Parse dates like 'Wednesday 18 February, 7 p.m.'"""
        text = text.strip()

        # "Wednesday 18 February, 7 p.m." or "Thursday 26 February, 7 p.m."
        m = re.match(r"\w+\s+(\d+)\s+(\w+),\s*(.+)", text)
        if m:
            day = int(m.group(1))
            month_str = m.group(2)
            time_raw = m.group(3).strip()

            # Parse time: "7 p.m." → "7pm"
            time_str = time_raw.replace(" ", "").replace(".", "").lower()

            months = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
            }
            month = months.get(month_str.lower())
            if month:
                year = date.today().year
                try:
                    d = date(year, month, day)
                    if d < date.today() - __import__("datetime").timedelta(days=60):
                        d = date(year + 1, month, day)
                    return d, time_str
                except ValueError:
                    pass

        return None, ""
