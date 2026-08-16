import json
import re
from datetime import date, datetime

from .base import BaseScraper, Event


# Focused search queries — social events where you actually meet people
SEARCHES = [
    "life-drawing",
    "gallery-opening",
    "creative-networking",
    "supper-club",
    "print-making-workshop",
    "design-talk",
    "art-opening",
    "private-view",
    "ai-meetup",
    "startup-founders",
    "politics",
    "debate",
    "philosophy",
]

# Searches whose results should be lensed as tech / writing regardless of
# Eventbrite's own category tag.
SEARCH_LENS = {
    "ai-meetup": "Tech",
    "startup-founders": "Tech",
    "politics": "Politics & Ideas",
    "debate": "Politics & Ideas",
    "philosophy": "Politics & Ideas",
}

# Skip events outside London proper
LONDON_AREAS = {
    "london", "shoreditch", "dalston", "hackney", "bethnal green",
    "peckham", "brixton", "camden", "islington", "soho", "fitzrovia",
    "clerkenwell", "whitechapel", "bermondsey", "deptford", "lewisham",
    "stratford", "bow", "mile end", "walthamstow", "tottenham",
    "stoke newington", "finsbury park", "king's cross", "angel",
    "south kensington", "chelsea", "fulham", "battersea", "vauxhall",
    "elephant and castle", "waterloo", "southwark", "borough",
    "hoxton", "haggerston", "hackney wick", "homerton",
    "somers town", "marylebone", "mayfair", "covent garden",
}

# Skip events with these words in the title
SKIP_WORDS = [
    "kids", "children", "family", "toddler", "baby", "under 5",
    "school", "gcse", "a-level", "teen",
]


class EventbriteScraper(BaseScraper):
    name = "Eventbrite"
    base_url = "https://www.eventbrite.co.uk"

    def scrape(self) -> list[Event]:
        events = []
        seen_ids = set()

        for search in SEARCHES:
            try:
                page_events = self._scrape_search(search, seen_ids)
                events.extend(page_events)
            except Exception as e:
                self.logger.error(f"Eventbrite search '{search}' failed: {e}")
        return events

    def _scrape_search(self, search_term: str, seen_ids: set) -> list[Event]:
        url = f"{self.base_url}/d/united-kingdom--london/{search_term}/?page=1"
        text = self._get_text(url, wait_ms=1500)

        # Extract __SERVER_DATA__ JSON
        m = re.search(r"window\.__SERVER_DATA__\s*=\s*({.*?});\s*\n", text, re.DOTALL)
        if not m:
            return []

        data = json.loads(m.group(1))
        results = data.get("search_data", {}).get("events", {}).get("results", [])

        events = []
        for item in results:
            eid = item.get("id", "")
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            name = (item.get("name") or "").strip()
            event_url = item.get("url", "")
            summary = (item.get("summary") or "").strip()
            start_str = item.get("start_date", "")
            start_time = item.get("start_time", "")

            if not name or not event_url:
                continue

            # Parse date
            start_date = None
            if start_str:
                try:
                    start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Format time
            time_str = ""
            if start_time:
                try:
                    t = datetime.strptime(start_time, "%H:%M:%S")
                    time_str = t.strftime("%-I:%M%p").lower()
                except ValueError:
                    time_str = start_time

            # Venue and area
            venue_info = item.get("primary_venue") or {}
            venue_name = venue_info.get("name", "")
            address = venue_info.get("address", {})
            area = address.get("localized_area_display", "")
            postcode = (address.get("postal_code") or "").strip().upper()
            img = (item.get("image") or {}).get("url", "") if isinstance(item.get("image"), dict) else ""

            # Category from tags (search lens wins)
            category = SEARCH_LENS.get(search_term, "")
            if not category:
                for tag in item.get("tags", []):
                    if tag.get("prefix") == "EventbriteCategory":
                        category = tag.get("display_name", "")
                        break

            # Skip online-only events
            if item.get("is_online_event"):
                continue

            # Skip events outside London
            area_lower = area.lower()
            city = address.get("city", "").lower()
            if area_lower and city:
                if not any(loc in area_lower or loc in city for loc in LONDON_AREAS):
                    continue

            # Skip kids/family events
            name_lower = name.lower()
            if any(w in name_lower for w in SKIP_WORDS):
                continue

            display_venue = venue_name if venue_name else "Eventbrite"

            # Free?
            price = item.get("ticket_availability") or {}
            is_free = bool(price.get("is_free")) if isinstance(price, dict) else False

            events.append(Event(
                title=name,
                venue=display_venue,
                url=event_url,
                start_date=start_date,
                time=time_str,
                description=summary[:200] if summary else "",
                category=category,
                area=area,
                is_free=is_free,
                source=self.name,
                postcode=postcode,
                image=img,
            ))

        return events
