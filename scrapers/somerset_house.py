import json
import re
from datetime import date, datetime

from .base import BaseScraper, Event


# Event types we want — skip exhibitions, music, screenings
INCLUDE_TYPES = {"talk", "workshop", "late-night", "event", "relaxed-session", "access-event"}


class SomersetHouseScraper(BaseScraper):
    name = "Somerset House"
    base_url = "https://www.somersethouse.org.uk"

    def scrape(self) -> list[Event]:
        events = []
        try:
            soup = self._get(f"{self.base_url}/whats-on")
            script = soup.find("script", id="props", type="application/json")
            if not script or not script.string:
                self.logger.warning("Somerset House: no props JSON found")
                return []

            # Fix invalid escape sequences in embedded HTML (e.g. \! in <!-- -->)
            raw = script.string
            data = json.loads(re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw))

            edges = data.get("data", {}).get("page", {}).get("items", {}).get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                title = node.get("title", "")
                url_path = node.get("url", "")
                if not title or not url_path:
                    continue

                # Filter by event type
                event_types = node.get("eventTypes") or []
                type_slugs = {t.get("slug", "") for t in event_types}
                if not type_slugs.intersection(INCLUDE_TYPES):
                    continue

                category = event_types[0].get("title", "") if event_types else ""

                # Dates
                start_str = node.get("dateStart", "")
                start_date = None
                if start_str:
                    try:
                        start_date = datetime.fromisoformat(start_str).date()
                    except ValueError:
                        pass

                # Skip past events
                if start_date and start_date < date.today():
                    continue

                description = (node.get("listingText") or "")[:200]
                is_free = node.get("priceFree", False)
                url = f"{self.base_url}{url_path}" if not url_path.startswith("http") else url_path

                events.append(Event(
                    title=title,
                    venue=self.name,
                    url=url,
                    start_date=start_date,
                    description=description,
                    category=category,
                    is_free=is_free,
                    area="Strand",
                ))

        except Exception as e:
            self.logger.error(f"Somerset House scrape failed: {e}")
        return events
