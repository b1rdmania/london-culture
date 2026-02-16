import re
from datetime import date

from .base import BaseScraper, Event


class BarbicanScraper(BaseScraper):
    name = "Barbican"
    base_url = "https://www.barbican.org.uk"

    def scrape(self) -> list[Event]:
        events = []
        try:
            # Scrape talks & events specifically (not cinema, not exhibitions)
            soup = self._get(f"{self.base_url}/whats-on/talks-events")
            for article in soup.select("article.listing--event"):
                link_el = article.select_one("a.search-listing__link")
                title_el = article.select_one("h2.listing-title")
                if not link_el or not title_el:
                    continue

                href = link_el.get("href", "")
                if not href.startswith("http"):
                    href = f"{self.base_url}{href}"

                title = title_el.get_text(strip=True)

                # Category from tags
                tags = [t.get_text(strip=True) for t in article.select("span.tag__plain")]
                category = ", ".join(tags) if tags else ""

                # Date/time from intro (format: "Tue 17 Feb 2026, 19:00")
                date_el = article.select_one("div.search-listing__intro p")
                start_date = None
                time_str = ""
                if date_el:
                    date_text = date_el.get_text(strip=True)
                    # Parse "Tue 17 Feb 2026, 19:00" or "Tue 17 Feb 2026"
                    m = re.search(r"(\d+)\s+(\w+)\s+(\d{4})(?:,\s*(\d+:\d+))?", date_text)
                    if m:
                        day, month_str, year = int(m.group(1)), m.group(2), int(m.group(3))
                        time_str = m.group(4) if m.group(4) else ""
                        months = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                                  "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
                        month = months.get(month_str)
                        if month:
                            try:
                                start_date = date(year, month, day)
                            except ValueError:
                                pass

                # Description (try other selectors, not the date one)
                desc_el = article.select_one("div.search-listing__intro div.typography, div.search-listing__description")
                desc = desc_el.get_text(strip=True)[:200] if desc_el else ""

                # Free?
                is_free = bool(article.select_one(".search-listing__label--promoted"))

                events.append(Event(
                    title=title,
                    venue=self.name,
                    url=href,
                    start_date=start_date,
                    time=time_str,
                    description=desc,
                    category=category,
                    is_free=is_free,
                    area="Barbican",
                ))
        except Exception as e:
            self.logger.error(f"Barbican scrape failed: {e}")
        return events
