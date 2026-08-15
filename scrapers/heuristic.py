"""Heuristic listing scraper for plain-HTML venue sites without schema.org.

For each anchor whose href matches `link_re`, walk up to the smallest
ancestor whose text contains a date, then pull title/date/time from it.
Good enough for WordPress/Drupal "what's on" grids.
"""
import re
from datetime import date
from urllib.parse import urljoin

from .base import BaseScraper, Event
from .galleries import DATE_RE, TIME_RE, MONTH_FIRST_RE, _date_from_text

NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")


class HeuristicListScraper(BaseScraper):
    urls: list[str] = []
    link_re: str = ""
    default_category: str = "Talks"
    default_area: str = ""
    max_events: int = 60
    skip_words = ("family", "children", "kids", "schools")
    free_by_default = False

    def category_for(self, title: str) -> str:
        t = title.lower()
        if any(w in t for w in ("workshop", "masterclass", "course", "class:")):
            return "Workshops"
        if any(w in t for w in ("politic", "democra", "philosoph", "econom", "war", "empire", "history", "law", "society", "power")):
            return "Politics & Ideas"
        if any(w in t for w in ("dance", "swing", "jukebox", "quiz", "social")):
            return "Social"
        if any(w in t for w in ("poetry", "book launch", "novel", "in conversation with")):
            return "Writing"
        return self.default_category

    def scrape(self) -> list[Event]:
        events, seen = [], set()
        pat = re.compile(self.link_re)
        for url in self.urls:
            try:
                soup = self._get(url)
            except Exception as e:
                self.logger.error(f"{self.name} fetch failed {url}: {e}")
                continue
            for a in soup.select("a[href]"):
                href = urljoin(url, a["href"]).split("#")[0]
                if not pat.search(href) or href in seen:
                    continue
                # climb to a container that carries a date
                node, text = a, ""
                for _ in range(7):
                    if node is None:
                        break
                    text = node.get_text(" ", strip=True)
                    if DATE_RE.search(text) or NUMERIC_DATE_RE.search(text) or MONTH_FIRST_RE.search(text):
                        break
                    node = node.parent
                else:
                    node = None
                if node is None or len(text) > 1500:
                    continue
                start = _date_from_text(text)
                if not start:
                    m = NUMERIC_DATE_RE.search(text)
                    if m:
                        try:
                            start = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                        except ValueError:
                            start = None
                if not start:
                    continue
                # title: heading in container, else the longest anchor text
                # pointing at the same href, else this anchor's text
                BAD = ("register", "read more", "find out more", "book now", "more info", "book", "tickets")
                title = ""
                for h in node.select("h1,h2,h3,h4"):
                    if h.get_text(" ", strip=True).lower() not in BAD:
                        title = h.get_text(" ", strip=True)
                        break
                if len(title) < 4:
                    # anchor title attribute like "Open Why Do We Need Empathy?"
                    for x in node.select("a[title]"):
                        if urljoin(url, x["href"]).split("#")[0] == href:
                            title = re.sub(r"^(open|view|read)\s+", "", x["title"].strip(), flags=re.I)
                            break
                if len(title) < 4:
                    same = [x.get_text(" ", strip=True) for x in node.select("a[href]")
                            if urljoin(url, x["href"]).split("#")[0] == href]
                    same = [x for x in same if x.lower() not in BAD]
                    title = max(same, key=len) if same else a.get_text(" ", strip=True)
                title = title.strip()
                if len(title) < 4:
                    continue
                tl = title.lower()
                if any(w in tl for w in self.skip_words):
                    continue
                seen.add(href)
                tm = TIME_RE.search(text)
                events.append(Event(
                    title=title, venue=self.name, url=href, start_date=start,
                    time=tm.group(1).lower().replace(" ", "") if tm else "",
                    category=self.category_for(title),
                    is_free=self.free_by_default or " free" in f" {text.lower()}",
                    area=self.default_area, source=self.name,
                ))
                if len(events) >= self.max_events:
                    return events
        return events


class HowToAcademyScraper(HeuristicListScraper):
    name = "How To Academy"
    urls = ["https://howtoacademy.com/events/"]
    link_re = r"howtoacademy\.com/events/[a-z0-9-]{6,}/?$"
    default_area = "London"
    default_category = "Politics & Ideas"
    skip_words = HeuristicListScraper.skip_words + ("livestream", "online")

    def category_for(self, title):
        t = title.lower()
        if any(w in t for w in ("comedy", "live on stage", "music")):
            return "Social"
        return super().category_for(title)


class GreshamScraper(HeuristicListScraper):
    name = "Gresham College"
    urls = ["https://www.gresham.ac.uk/whats-on"]
    link_re = r"gresham\.ac\.uk/whats-on/(?!venues|accessibility)[a-z0-9-]{4,}/?$"
    default_category = "Talks"
    default_area = "Holborn"
    free_by_default = True


class BishopsgateScraper(HeuristicListScraper):
    name = "Bishopsgate Institute"
    urls = ["https://www.bishopsgate.org.uk/whats-on"]
    link_re = r"bishopsgate\.org\.uk/whats-on/(activity|event|course|talk)s?/[a-z0-9-]{4,}/?$"
    default_area = "Liverpool Street"
