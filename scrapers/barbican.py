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

                # Description
                desc_el = article.select_one("div.search-listing__intro p")
                desc = ""
                if desc_el:
                    desc = desc_el.get_text(strip=True)[:200]

                # Free?
                is_free = bool(article.select_one(".search-listing__label--promoted"))

                events.append(Event(
                    title=title,
                    venue=self.name,
                    url=href,
                    description=desc,
                    category=category,
                    is_free=is_free,
                    area="Barbican",
                ))
        except Exception as e:
            self.logger.error(f"Barbican scrape failed: {e}")
        return events
