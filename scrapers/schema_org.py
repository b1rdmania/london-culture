"""Generic scraper for sites that embed schema.org Event JSON-LD.

Subclasses set `name`, `urls`, `default_category` and optionally override
`accept()`; everything else is shared.
"""
import html
import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

from bs4 import BeautifulSoup

from .base import BaseScraper, Event


def _walk_events(node, acc):
    if isinstance(node, dict):
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if any(isinstance(x, str) and x.endswith("Event") for x in types):
            acc.append(node)
        for v in node.values():
            _walk_events(v, acc)
    elif isinstance(node, list):
        for v in node:
            _walk_events(v, acc)


def _parse_dt(s: str):
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _strip_html(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class SchemaOrgScraper(BaseScraper):
    urls: list[str] = []
    default_category: str = ""
    default_area: str = ""
    max_span_days: int = 3      # skip "ongoing" events longer than this
    wait_ms: int = 0
    max_events: int = 200

    def accept(self, ev: dict, title: str) -> bool:
        return True

    def venue_for(self, ev: dict) -> str:
        loc = ev.get("location")
        if isinstance(loc, list):
            loc = loc[0] if loc else None
        if isinstance(loc, dict):
            n = loc.get("name")
            if n:
                return _strip_html(n)
        return self.name

    def area_for(self, ev: dict) -> str:
        loc = ev.get("location")
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict):
                return addr.get("addressLocality") or self.default_area
        return self.default_area

    def category_for(self, ev: dict, title: str) -> str:
        return self.default_category

    def scrape(self) -> list[Event]:
        events, seen = [], set()
        for url in self.urls:
            try:
                text = self._get_text(url, wait_ms=self.wait_ms)
            except Exception as e:
                self.logger.error(f"{self.name} fetch failed {url}: {e}")
                continue
            soup = BeautifulSoup(text, "html.parser")
            raw = []
            for sc in soup.select('script[type="application/ld+json"]'):
                if not sc.string:
                    continue
                try:
                    _walk_events(json.loads(sc.string), raw)
                except json.JSONDecodeError:
                    continue
            for ev in raw:
                e = self._to_event(ev, soup, url)
                if e and e.url not in seen:
                    seen.add(e.url)
                    events.append(e)
        return events[: self.max_events]

    def _to_event(self, ev: dict, soup=None, page_url: str = ""):
        title = _strip_html(ev.get("name", ""))
        url = ev.get("url") or ev.get("@id") or ""
        if not url and soup is not None:
            # Some sites (Conway Hall) omit url from JSON-LD; find the anchor by title.
            key = title[:25].lower()
            for a in soup.select("a[href]"):
                if key and key in a.get_text(" ", strip=True).lower():
                    url = urljoin(page_url, a["href"])
                    break
        if not title or not url:
            return None
        start = _parse_dt(ev.get("startDate", ""))
        end = _parse_dt(ev.get("endDate", ""))
        if not start:
            return None
        if start.tzinfo is not None:
            start = start.astimezone(LONDON)
        if end is not None and end.tzinfo is not None:
            end = end.astimezone(LONDON)
        if end and (end.date() - start.date()).days > self.max_span_days:
            return None
        mode = ev.get("eventAttendanceMode", "") or ""
        if "Online" in mode:
            return None
        if not self.accept(ev, title):
            return None
        offers = ev.get("offers")
        if isinstance(offers, dict):
            offers = [offers]
        is_free = False
        if isinstance(offers, list):
            for o in offers:
                if isinstance(o, dict):
                    p = str(o.get("price", "")).strip().lower()
                    if p in ("0", "0.0", "0.00", "free"):
                        is_free = True
        time_str = start.strftime("%-I:%M%p").lower().replace(":00", "")
        return Event(
            title=title,
            venue=self.venue_for(ev),
            url=url,
            start_date=start.date(),
            end_date=end.date() if end else None,
            time=time_str,
            description=_strip_html(ev.get("description", ""))[:220],
            category=self.category_for(ev, title),
            is_free=is_free,
            area=self.area_for(ev),
            source=self.name,
        )


class LumaScraper(SchemaOrgScraper):
    """lu.ma/london — where London's tech/founder scene actually lists things."""
    name = "Luma"
    urls = ["https://lu.ma/london"]
    default_category = "Tech"
    default_area = "London"
    SKIP = ("hnwi", "networking breakfast", "networking b", "crypto mondays")

    def accept(self, ev, title):
        t = title.lower()
        return not any(w in t for w in self.SKIP)

    def category_for(self, ev, title):
        t = title.lower()
        if any(w in t for w in ("dinner", "drinks", "social", "mixer", "party", "brunch")):
            return "Social"
        return "Tech"


class ConwayHallScraper(SchemaOrgScraper):
    """Conway Hall — talks, debates, Sunday lectures, Ethical Society."""
    name = "Conway Hall"
    urls = ["https://conwayhall.org.uk/whats-on/"]
    default_category = "Talks"
    default_area = "Holborn"

    def venue_for(self, ev):
        return "Conway Hall"

    def accept(self, ev, title):
        t = title.lower()
        return not any(w in t for w in ("concert", "recital", "chamber music", "film screening"))

    def category_for(self, ev, title):
        t = title.lower()
        if any(w in t for w in ("workshop", "course", "class")):
            return "Workshops"
        if any(w in t for w in ("poetry", "book launch", "reading")):
            return "Writing"
        if any(w in t for w in ("politic", "democra", "philosoph", "ethic", "econom", "war", "history", "society", "debate")):
            return "Politics & Ideas"
        return "Talks"


class MeetupScraper(SchemaOrgScraper):
    """Meetup find pages embed schema.org for the first page of results."""
    name = "Meetup"
    urls = [
        "https://www.meetup.com/find/?location=gb--17--London&source=EVENTS&categoryId=546",  # tech
        "https://www.meetup.com/find/?location=gb--17--London&source=EVENTS&keywords=ai",
        "https://www.meetup.com/find/?location=gb--17--London&source=EVENTS&keywords=art%20gallery",
        "https://www.meetup.com/find/?location=gb--17--London&source=EVENTS&keywords=politics",
        "https://www.meetup.com/find/?location=gb--17--London&source=EVENTS&keywords=philosophy",
    ]
    default_category = "Tech"
    default_area = "London"

    def category_for(self, ev, title):
        t = title.lower()
        org = ""
        o = ev.get("organizer")
        if isinstance(o, dict):
            org = (o.get("name") or "").lower()
        blob = f"{t} {org}"
        if any(w in blob for w in ("politic", "philosoph", "debate", "current affairs", "geopolit", "econom")):
            return "Politics & Ideas"
        if any(w in blob for w in ("writ", "poet", "book", "novel", "author")):
            return "Writing"
        if any(w in blob for w in ("gallery", "art ", "sketch", "drawing", "museum")):
            return "Art & Design"
        if any(w in blob for w in ("social", "drinks", "pub", "meet new")):
            return "Social"
        return "Tech"


class PoetrySocietyScraper(SchemaOrgScraper):
    name = "Poetry Society"
    urls = ["https://poetrysociety.org.uk/events/"]
    default_category = "Writing"
    default_area = "Covent Garden"
    max_span_days = 1  # their listing carries perpetual 1-2-1 sessions
