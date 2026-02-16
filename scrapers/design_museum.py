import re
from datetime import date, datetime

from .base import BaseScraper, Event


class DesignMuseumScraper(BaseScraper):
    name = "Design Museum"
    base_url = "https://designmuseum.org"

    def scrape(self) -> list[Event]:
        events = []
        try:
            # Talks, courses & workshops — not exhibitions
            soup = self._get(f"{self.base_url}/whats-on/talks-courses-and-workshops")
            for item in soup.select("div.page-item"):
                time_el = item.select_one("time.icon-date")
                title_el = item.select_one("h2")
                link_el = item.select_one("a[href]")

                if not title_el or not link_el:
                    continue

                title = title_el.get_text(strip=True)

                # Skip kids events and non-events
                title_lower = title.lower()
                skip_words = [
                    "year old", "children", "kids", "family", "toddler", "baby",
                    "schools", "sign up", "newsletter", "plan your visit",
                    "members enjoy", "membership", "ma curating",
                ]
                if any(w in title_lower for w in skip_words):
                    continue

                href = link_el["href"]
                if not href.startswith("http"):
                    href = f"{self.base_url}{href}"

                date_text = time_el.get_text(strip=True) if time_el else ""
                event_date, time_str = self._parse_datetime(date_text)

                desc_el = item.select_one("div.rich-text p")
                desc = ""
                if desc_el:
                    desc = desc_el.get_text(strip=True)[:200]
                    desc = re.sub(r"\s*Sold out\..*$", "", desc)

                is_free = "free" in date_text.lower() if date_text else False

                events.append(Event(
                    title=title,
                    venue=self.name,
                    url=href,
                    start_date=event_date,
                    time=time_str,
                    description=desc,
                    category="Talk / Workshop",
                    is_free=is_free,
                    area="Kensington",
                ))
        except Exception as e:
            self.logger.error(f"Design Museum scrape failed: {e}")
        return events

    def _parse_datetime(self, text: str) -> tuple[date | None, str]:
        """Parse dates like 'Tuesday 17 February, 10:00 – 16:00' or 'Thursday 6 March 2026, 19:00 – 20:30'."""
        # Extract time range
        time_str = ""
        time_match = re.search(r"(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})", text)
        if time_match:
            start_t = time_match.group(1)
            end_t = time_match.group(2)
            try:
                s = datetime.strptime(start_t, "%H:%M").strftime("%-I:%M%p").lower()
                e = datetime.strptime(end_t, "%H:%M").strftime("%-I:%M%p").lower()
                time_str = f"{s} – {e}"
            except ValueError:
                time_str = f"{start_t} – {end_t}"

        # Extract date
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }
        m = re.search(r"(\d+)\s+(\w+)(?:\s+(\d{4}))?", text)
        if m:
            day = int(m.group(1))
            month = months.get(m.group(2).lower())
            year = int(m.group(3)) if m.group(3) else date.today().year
            if month:
                try:
                    return date(year, month, day), time_str
                except ValueError:
                    pass

        return None, time_str
