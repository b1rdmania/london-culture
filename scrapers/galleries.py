"""East/North London galleries: listing page → event links → detail page."""
import json
import re
from datetime import date

from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from .schema_org import _walk_events, _parse_dt, _strip_html

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_RE = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?,?\s+(\d{1,2})\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+(\d{4}))?", re.I)
MONTH_FIRST_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b(?!\s*(?:am|pm|:))(?:,?\s+(\d{4}))?", re.I)
TIME_RE = re.compile(r"\b(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm))\b", re.I)


def _date_from_text(text: str):
    m = DATE_RE.search(text)
    if m:
        day, mon, yr = int(m.group(1)), MONTHS[m.group(2).lower()[:3]], m.group(3)
    else:
        m = MONTH_FIRST_RE.search(text)
        if not m:
            return None
        day, mon, yr = int(m.group(2)), MONTHS[m.group(1).lower()[:3]], m.group(3)
    today = date.today()
    year = int(yr) if yr else today.year
    try:
        d = date(year, mon, day)
    except ValueError:
        return None
    if not yr and d < today:
        d = date(year + 1, mon, day)
    return d


class WhitechapelScraper(BaseScraper):
    name = "Whitechapel Gallery"
    base_url = "https://www.whitechapelgallery.org"

    def scrape(self) -> list[Event]:
        events = []
        try:
            soup = self._get(f"{self.base_url}/events/")
        except Exception as e:
            self.logger.error(f"Whitechapel listing failed: {e}")
            return events
        links = []
        for a in soup.select("a[href*='/events/']"):
            href = a.get("href", "")
            if re.search(r"/events/[a-z0-9-]{4,}/?$", href) and href not in links:
                links.append(href)
        for href in links[:25]:
            try:
                page = self._get(href)
            except Exception as e:
                self.logger.warning(f"Whitechapel detail failed {href}: {e}")
                continue
            title_el = page.select_one("h1")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            text = page.get_text(" ", strip=True)
            start = _date_from_text(text)
            if not title or not start:
                continue
            tl = title.lower()
            if any(w in tl for w in ("family", "children", "kids", "highlight tours")):
                continue
            tm = TIME_RE.search(text)
            desc_el = page.select_one("meta[property='og:description']")
            events.append(Event(
                title=title, venue=self.name, url=href, start_date=start,
                time=tm.group(1).lower().replace(" ", "") if tm else "",
                description=(desc_el.get("content", "") if desc_el else "")[:220],
                category=self._cat(tl), is_free="free" in text.lower()[:3000],
                area="Whitechapel", source=self.name,
            ))
        return events

    @staticmethod
    def _cat(t):
        if any(w in t for w in ("late", "opening", "private view", "launch")):
            return "Openings"
        if any(w in t for w in ("workshop", "make ", "drawing", "walk")):
            return "Workshops"
        return "Talks"


class CamdenArtCentreScraper(BaseScraper):
    """Detail pages carry schema.org Event; the listing does not."""
    name = "Camden Art Centre"
    base_url = "https://camdenartcentre.org"

    def scrape(self) -> list[Event]:
        events = []
        try:
            soup = self._get(f"{self.base_url}/whats-on/in-the-building")
        except Exception as e:
            self.logger.error(f"Camden listing failed: {e}")
            return events
        links = []
        for a in soup.select("a[href*='/whats-on/']"):
            href = a.get("href", "").split("?")[0]
            if href.startswith("/"):
                href = self.base_url + href
            if re.search(r"/whats-on/[a-z0-9-]{4,}$", href) and href not in links \
                    and not href.endswith(("in-the-building", "on-demand", "offsite", "archive")):
                links.append(href)
        for href in links[:25]:
            try:
                text = self._get_text(href)
            except Exception as e:
                self.logger.warning(f"Camden detail failed {href}: {e}")
                continue
            page = BeautifulSoup(text, "html.parser")
            raw = []
            for sc in page.select('script[type="application/ld+json"]'):
                try:
                    _walk_events(json.loads(sc.string or ""), raw)
                except json.JSONDecodeError:
                    pass
            if not raw:
                continue
            ev = raw[0]
            start, end = _parse_dt(ev.get("startDate", "")), _parse_dt(ev.get("endDate", ""))
            if not start:
                continue
            if end and (end.date() - start.date()).days > 3:
                continue  # exhibition run, not an evening
            title = _strip_html(ev.get("name", ""))
            tl = title.lower()
            if any(w in tl for w in ("family", "children", "kids")):
                continue
            events.append(Event(
                title=title, venue=self.name, url=href, start_date=start.date(),
                end_date=end.date() if end else None,
                time=start.strftime("%-I:%M%p").lower().replace(":00", ""),
                description=_strip_html(ev.get("description", ""))[:220],
                category="Workshops" if any(w in tl for w in ("workshop", "drawing", "class")) else "Talks",
                area="Finchley Road", source=self.name,
            ))
        return events
