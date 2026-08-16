#!/usr/bin/env python3
"""London Culture — daily digest of talks, openings, workshops, tech and
politics events in London worth leaving the house for."""

import json
import logging
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader

from scrapers import (
    RichMixScraper, EventbriteScraper, BarbicanScraper, DesignMuseumScraper,
    ICAScraper, WellcomeScraper, PhotographersGalleryScraper, SomersetHouseScraper,
    LRBBookshopScraper, VAMScraper,
    LumaScraper, ConwayHallScraper, MeetupScraper, PoetrySocietyScraper,
    WhitechapelScraper, CamdenArtCentreScraper,
)
from scrapers.heuristic import GreshamScraper, BishopsgateScraper, HowToAcademyScraper
from scrapers.base import BROWSER_UA, Event
from score import score_events

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"
PAGE_URL = (os.environ.get("PAGE_URL") or "https://b1rdmania.github.io/london-culture").rstrip("/")

# Categories to exclude globally
EXCLUDE_CATEGORIES = {
    "music", "cinema", "film", "gigs", "live events",
    "music / performance", "classical music", "contemporary music",
    "performing & visual arts",
}

# Scrapers that need a rendered page (JS lists) — get the Playwright page up front.
BROWSER_ONLY = {GreshamScraper, BishopsgateScraper}

SCRAPERS = [
    # institutions
    BarbicanScraper, DesignMuseumScraper, WellcomeScraper, PhotographersGalleryScraper,
    SomersetHouseScraper, VAMScraper, ICAScraper, RichMixScraper,
    # galleries
    WhitechapelScraper,
    # talks / politics / ideas
    ConwayHallScraper, GreshamScraper, BishopsgateScraper, HowToAcademyScraper,
    # tech / scene
    LumaScraper, MeetupScraper, EventbriteScraper,
]


def scrape_all():
    """Run every scraper, sharing one Playwright page as a fallback."""
    all_events, health = [], []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        logging.warning("Playwright not installed — browser fallback disabled")

    def run(page):
        for S in SCRAPERS:
            s = S()
            s.page = page
            if S in BROWSER_ONLY and page is not None:
                s._get_text = lambda url, wait_ms=0, s=s: s._browser_text(url, wait_ms or 4000)
            try:
                events = s.scrape(page=page) if S is ICAScraper else s.scrape()
            except Exception as e:
                logging.error(f"{s.name} crashed: {e}")
                events = []
            for e in events:
                if not e.source:
                    e.source = s.name
            logging.info(f"{s.name}: {len(events)} events")
            health.append((s.name, len(events)))
            all_events.extend(events)

    if sync_playwright:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(
                user_agent=BROWSER_UA, locale="en-GB", timezone_id="Europe/London",
                viewport={"width": 1366, "height": 900})
            ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = ctx.new_page()
            run(page)
            browser.close()
    else:
        run(None)
    return all_events, health


TITLE_SKIP = [
    "concert", "gig:", "dj set", "live band",
    "family workshop", "design baby", "kids", "children", "toddler", "baby",
    "under 5", "school of", "schools live", "play after school", "sound explorers",
    "mini jam", "teacher drop-in", "ks1", "ks2", "eyfs", "(livestream)",
    "youth festival", "young poets", "family-friendly",
    "hnwi", "networking breakfast", "business breakfast",
    "general admission", "entry ticket", "admission ticket",
    "run club", "running club", "jog", "5k", "10k", "parkrun", "marathon",
    "private equity", "venture capital", " vc ", "investor", "wealth",
    "black history", "equality", "diversity", "inclusion", "dei ",
    "live painting", "poetry", "spoken word", "ceramic", "pottery",
    "writing", "writers", "write-in", "shut up and write", "book club", "book launch", "novel", "memoir",
    "bsl ", "audio described", "livestream", "quartet", "trio", "recital", "conference", "ages 7",
    "menopause", "toastmasters", "hike", "run club", "sold out",
    "africa", "african", "private credit", "influencer", "marketing", "vibe coding", "meditation",
    "black heritage", "black &", "black and mixed", "diaspora", "coached running", "stride:",
]


# Central / north / east only. Decide by outward postcode when we have one,
# else by area/venue words. Unknown location = keep.
OK_DISTRICT_PREFIX = ("E", "EC", "N", "NW", "WC")
OK_DISTRICTS = {"SE1", "SE11", "SE16", "SE17", "SW1", "SW1A", "SW1E", "SW1H", "SW1P", "SW1V", "SW1W", "SW1X", "SW1Y",
                "SW3", "SW7", "W1", "W2", "W8", "W9", "W10", "W11", "SW10", "SW5", "SW6"}
BAD_AREAS = [
    "dulwich", "peckham", "brixton", "clapham", "croydon", "wimbledon", "richmond", "ealing",
    "hounslow", "harrow", "uxbridge", "kingston", "sutton", "bromley", "lewisham", "catford",
    "greenwich", "woolwich", "streatham", "tooting", "balham", "putney", "twickenham", "acton",
    "chiswick", "wembley", "barnet", "enfield", "romford", "ilford", "barking", "dagenham",
    "bexley", "orpington", "surbiton", "new malden", "mitcham", "morden", "eltham", "sidcup",
    "forest hill", "sydenham", "crystal palace", "norwood", "herne hill", "camberwell",
    "deptford", "new cross", "nunhead", "elephant", "kennington", "vauxhall", "battersea",
    "wandsworth", "hammersmith", "shepherd", "white city", "kensal", "willesden", "kilburn",
    "watford", "brighton", "croydon", "essex", "surrey", "kent", "hertford", "reading", "oxford",
    "cambridge", "birmingham", "manchester", "bristol", "edinburgh", "glasgow", "leeds",
]


def _district(pc: str) -> str:
    m = re.match(r"^([A-Z]{1,2}\d[A-Z\d]?)", (pc or "").upper().replace(" ", ""))
    return m.group(1) if m else ""


def in_zone(e) -> bool:
    d = _district(e.postcode)
    if d:
        if d in OK_DISTRICTS:
            return True
        letters = re.match(r"^[A-Z]+", d).group(0)
        if letters in OK_DISTRICT_PREFIX:
            return True
        return False
    blob = f"{e.title} {e.area} {e.venue} {e.description[:120]}".lower()
    return not any(a in blob for a in BAD_AREAS)


def filter_events(events):
    """Remove music/cinema/kids/spam, deduplicate, sort by date."""
    today = date.today()
    horizon = today + timedelta(days=90)
    filtered = []
    for e in events:
        if not e.start_date or e.start_date < today or e.start_date > horizon:
            continue
        cat = e.category.lower().strip()
        if any(part.strip() in EXCLUDE_CATEGORIES for part in cat.split(",")):
            continue
        t = e.title.lower()
        if any(w in t for w in TITLE_SKIP):
            continue
        if not in_zone(e):
            continue
        filtered.append(e)

    seen, unique = set(), []
    for e in filtered:
        key = (e.title.lower().strip(), e.start_date)
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return sorted(unique, key=lambda e: (e.start_date, e.time or ""))


LENSES = ["Talks", "Politics & Ideas", "Tech", "Openings", "Workshops", "Social"]


def normalize_category(cat: str, title: str = "") -> str:
    """Map raw categories to the interest lenses used on the page."""
    c = cat.lower().strip()
    t = title.lower()
    if c in {l.lower() for l in LENSES}:
        return next(l for l in LENSES if l.lower() == c)
    if any(w in c or w in t for w in ["politic", "democra", "philosoph", "geopolit", "debate", "economy", "economics"]):
        return "Politics & Ideas"
    if any(w in c or w in t for w in ["tech", "startup", "founder", "ai ", "a.i.", "software", "developer", "coding"]):
        return "Tech"
    if any(w in c for w in ["opening", "private view", "late"]) or any(w in t for w in ["private view", "opening", "friday late", "late:"]):
        return "Openings"
    if any(w in c for w in ["workshop", "class", "course", "drawing", "make"]) or any(w in t for w in ["workshop", "life drawing", "masterclass"]):
        return "Workshops"
    if any(w in c for w in ["network", "social", "meet", "supper", "drinks", "quiz"]) or any(w in t for w in ["supper club", "drinks", "quiz", "social"]):
        return "Social"
    if any(w in c for w in ["talk", "lecture", "conversation", "panel", "discussion", "tour", "art", "visual", "design", "exhibition"]):
        return "Talks"
    return "Talks" if any(w in t for w in ["talk", "in conversation", "lecture", "panel"]) else "Other"


def load_previous():
    """Previous run's events, from the live site or local data.
    Returns (first_seen map by url, raw rows)."""
    prev = {}
    for src in (f"{PAGE_URL}/events.json", DATA / "events.json"):
        try:
            if isinstance(src, str):
                r = requests.get(src, timeout=15)
                if r.status_code != 200:
                    continue
                rows = r.json()
            else:
                rows = json.loads(src.read_text())
            for row in rows:
                if row.get("url"):
                    prev[row["url"]] = row.get("first_seen") or row.get("_run") or ""
            if prev:
                logging.info(f"Loaded {len(prev)} previous events from {src}")
                return prev, rows
        except Exception as e:
            logging.warning(f"Could not load previous events from {src}: {e}")
    return prev, []


def carry_forward(events, health, prev_rows, run_day):
    """If a source returned 0 this run (blocked, site changed), keep its
    previously published future events rather than dropping them all.
    Cap staleness at 10 days so a dead source fades out."""
    zero = {n for n, c in health if c == 0}
    if not zero or not prev_rows:
        return events, health
    carried = 0
    for row in prev_rows:
        if row.get("source") not in zero or not row.get("start_date"):
            continue
        try:
            sd = date.fromisoformat(row["start_date"])
            last_ok = date.fromisoformat(row.get("_run") or row.get("first_seen"))
        except (TypeError, ValueError):
            continue
        if sd < run_day or (run_day - last_ok).days > 10:
            continue
        e = Event(
            title=row["title"], venue=row.get("venue", ""), url=row["url"],
            start_date=sd, time=row.get("time", ""), description=row.get("description", ""),
            category=row.get("category", ""), is_free=bool(row.get("is_free")),
            area=row.get("area", ""), source=row["source"],
            postcode=row.get("postcode", ""), image=row.get("image", ""),
        )
        e._carried_run = row.get("_run") or row.get("first_seen")
        events.append(e)
        carried += 1
    if carried:
        logging.warning(f"Carried forward {carried} events from blocked sources: {', '.join(sorted(zero))}")
        health = [(n, c if n not in zero else f"0 (kept {sum(1 for e in events if getattr(e, '_carried_run', None) and e.source == n)})") for n, c in health]
    return events, health


def annotate(events, prev, run_day):
    """Set lens, first_seen, is_new. 'New' = first seen within the last 7 days."""
    cutoff = run_day - timedelta(days=7)
    baseline = (not prev) or "--rebaseline" in sys.argv  # nothing is "new"
    default_seen = (run_day - timedelta(days=8)).isoformat() if baseline else run_day.isoformat()
    for e in events:
        e._lens = normalize_category(e.category, e.title)
        fs = (None if baseline else prev.get(e.url)) or default_seen
        e._first_seen = fs
        try:
            e._is_new = (not baseline) and date.fromisoformat(fs) > cutoff
        except ValueError:
            e._is_new = not baseline
    return events


def build_html(events, health, run_day, picks=()):
    OUTPUT.mkdir(exist_ok=True)
    sources = sorted({e.source for e in events})
    lenses = [l for l in LENSES if any(e._lens == l for e in events)]
    if any(e._lens == "Other" for e in events):
        lenses.append("Other")
    weekend = [d for d in range(0, 8) if (run_day + timedelta(days=d)).weekday() >= 5][:2]
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    html = env.get_template("page.html").render(
        events=events, sources=sources, lenses=lenses, health=health, picks=picks,
        scored=sum(1 for e in events if e._score is not None),
        mixed_count=sum(1 for e in events if getattr(e, "_mixed", False)),
        today=run_day.isoformat(),
        week_end=(run_day + timedelta(days=7)).isoformat(),
        weekend_start=(run_day + timedelta(days=weekend[0])).isoformat() if weekend else run_day.isoformat(),
        weekend_end=(run_day + timedelta(days=weekend[-1])).isoformat() if weekend else run_day.isoformat(),
        new_count=sum(1 for e in events if e._is_new),
        free_count=sum(1 for e in events if e.is_free),
        updated_at=datetime.now().strftime("%-d %B %Y, %H:%M"),
    )
    (OUTPUT / "index.html").write_text(html)
    logging.info(f"Built {OUTPUT / 'index.html'} ({len(events)} events)")


def build_email(events):
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    return env.get_template("email.html").render(
        events=[e for e in events if e._is_new][:40] or events[:40],
        week_of=date.today().strftime("%-d %B %Y"),
        page_url=PAGE_URL,
    )


def send_email(html):
    api_key = os.environ.get("RESEND_API_KEY")
    to_email = os.environ.get("DIGEST_EMAIL")
    if not api_key or not to_email:
        logging.warning("RESEND_API_KEY or DIGEST_EMAIL not set — skipping email")
        return
    import resend
    resend.api_key = api_key
    resend.Emails.send({
        "from": os.environ.get("FROM_EMAIL", "London Culture <onboarding@resend.dev>"),
        "to": [to_email],
        "subject": f"London Culture — {date.today().strftime('%-d %b %Y')}",
        "html": html,
    })
    logging.info(f"Email sent to {to_email}")


def save_events(events, health, run_day):
    """Persist to data/ and output/ (output is what the next run reads back)."""
    rows = [
        {
            "title": e.title, "venue": e.venue, "url": e.url, "source": e.source,
            "start_date": e.start_date.isoformat() if e.start_date else None,
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "time": e.time, "description": e.description, "category": e.category,
            "lens": e._lens, "is_free": e.is_free, "area": e.area,
            "first_seen": e._first_seen,
            "score": getattr(e, "_score", None), "why": getattr(e, "_why", ""),
            "mixed": getattr(e, "_mixed", False), "tag": getattr(e, "_tag", ""),
            "postcode": e.postcode, "image": e.image,
            "_run": getattr(e, "_carried_run", None) or run_day.isoformat(),
        }
        for e in events
    ]
    DATA.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    payload = json.dumps(rows, indent=1)
    (DATA / "events.json").write_text(payload)
    (OUTPUT / "events.json").write_text(payload)
    (OUTPUT / "health.json").write_text(json.dumps(
        {"run": run_day.isoformat(), "sources": dict(health)}, indent=1))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    run_day = date.today()
    prev, prev_rows = load_previous()
    events, health = scrape_all()
    events, health = carry_forward(events, health, prev_rows, run_day)
    events = filter_events(events)
    events = annotate(events, prev, run_day)
    score_events(events, prev_rows)
    picks = [e for e in events if (e._score or 0) >= 8 and e.start_date <= run_day + timedelta(days=14)]
    picks.sort(key=lambda e: (-(e._score or 0), e.start_date))
    logging.info(f"Total: {len(events)} events, {sum(1 for e in events if e._is_new)} new")
    zero = [n for n, c in health if str(c).startswith("0")]
    if zero:
        logging.warning(f"Sources returning 0: {', '.join(zero)}")
    save_events(events, health, run_day)
    build_html(events, health, run_day, picks[:8])
    if "--email" in sys.argv:
        send_email(build_email(events))


if __name__ == "__main__":
    main()
