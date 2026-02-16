import re
from datetime import date, datetime

from .base import BaseScraper, Event


# Event types we want from V&A — skip general exhibitions
INCLUDE_TYPES = {"talk", "drop-in", "special event", "workshop", "late", "performance"}


class VAMScraper(BaseScraper):
    name = "V&A"
    base_url = "https://www.vam.ac.uk"

    def scrape(self) -> list[Event]:
        events = []
        try:
            soup = self._get(f"{self.base_url}/whatson")
            seen_hrefs = set()

            # Featured events
            for card in soup.select("[class*='b-events-featured']"):
                event = self._parse_featured(card, seen_hrefs)
                if event:
                    events.append(event)

            # Regular teasers
            for card in soup.select("a[href*='/event/']"):
                event = self._parse_teaser(card, seen_hrefs)
                if event:
                    events.append(event)

        except Exception as e:
            self.logger.error(f"V&A scrape failed: {e}")
        return events

    def _parse_featured(self, card, seen_hrefs) -> Event | None:
        link = card.select_one("a[href*='/event/']")
        if not link:
            return None
        href = link.get("href", "")
        if href in seen_hrefs:
            return None
        seen_hrefs.add(href)

        title_el = card.select_one("h3.b-events-featured__title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        type_el = card.select_one("p.b-events-featured__type")
        event_type = type_el.get_text(strip=True).lower() if type_el else ""
        if event_type and event_type not in INCLUDE_TYPES:
            return None

        date_el = card.select_one("p.b-events-featured__date")
        date_text = date_el.get_text(strip=True) if date_el else ""
        start_date = self._parse_date(date_text)

        if start_date and start_date < date.today():
            return None

        venue_el = card.select_one("p.b-events-featured__venue")
        area = venue_el.get_text(strip=True) if venue_el else "South Kensington"

        url = f"{self.base_url}{href}" if not href.startswith("http") else href

        return Event(
            title=title,
            venue=self.name,
            url=url,
            start_date=start_date,
            category=event_type.title() if event_type else "",
            area=area,
        )

    def _parse_teaser(self, card, seen_hrefs) -> Event | None:
        href = card.get("href", "")
        if not href or "/event/" not in href:
            return None
        if href in seen_hrefs:
            return None
        seen_hrefs.add(href)

        title_el = card.select_one("h2.b-event-teaser__title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        type_el = card.select_one("div.b-event-teaser__type")
        event_type = type_el.get_text(strip=True).lower() if type_el else ""
        if event_type and event_type not in INCLUDE_TYPES:
            return None

        # Date and venue from icon list items
        icon_items = card.select("p.b-icon-list__item-text")
        date_text = icon_items[0].get_text(strip=True) if len(icon_items) > 0 else ""
        area = icon_items[1].get_text(strip=True) if len(icon_items) > 1 else "South Kensington"

        start_date = self._parse_date(date_text)
        if start_date and start_date < date.today():
            return None

        # Check sold out
        sold_out = card.select_one("div.u-label-tag--sold-out")

        url = f"{self.base_url}{href}" if not href.startswith("http") else href

        return Event(
            title=title,
            venue=self.name,
            url=url,
            start_date=start_date,
            category=event_type.title() if event_type else "",
            area=area,
        )

    def _parse_date(self, text: str) -> date | None:
        """Parse dates like 'Friday, 27 February 2026'."""
        text = text.strip()
        m = re.search(r"(\d+)\s+(\w+)\s+(\d{4})", text)
        if m:
            day, month_str, year = int(m.group(1)), m.group(2), int(m.group(3))
            months = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
            }
            month = months.get(month_str.lower())
            if month:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass
        return None
