#!/usr/bin/env python3
"""London Culture — weekly digest of creative social events worth going to."""

import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from scrapers import (
    RichMixScraper,
    EventbriteScraper,
    BarbicanScraper,
    DesignMuseumScraper,
    ICAScraper,
    WellcomeScraper,
    PhotographersGalleryScraper,
    SomersetHouseScraper,
    LRBBookshopScraper,
    VAMScraper,
)

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"

# Categories to exclude globally
EXCLUDE_CATEGORIES = {
    "music", "cinema", "film", "gigs", "live events",
    "music / performance", "classical music", "contemporary music",
    "performing & visual arts",
}


def scrape_simple():
    """Run the requests-based scrapers."""
    scrapers = [
        RichMixScraper(),
        EventbriteScraper(),
        BarbicanScraper(),
        DesignMuseumScraper(),
        WellcomeScraper(),
        PhotographersGalleryScraper(),
        SomersetHouseScraper(),
        LRBBookshopScraper(),
        VAMScraper(),
    ]
    all_events = []
    for s in scrapers:
        events = s.scrape()
        logging.info(f"{s.name}: {len(events)} events")
        all_events.extend(events)
    return all_events


def scrape_browser():
    """Run Playwright-based scrapers."""
    browser_scrapers = [ICAScraper()]
    all_events = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            for s in browser_scrapers:
                events = s.scrape(page=page)
                logging.info(f"{s.name}: {len(events)} events")
                all_events.extend(events)
            browser.close()
    except ImportError:
        logging.warning("Playwright not installed — skipping ICA")
    except Exception as e:
        logging.error(f"Browser scraping failed: {e}")
    return all_events


def filter_events(events):
    """Remove music/cinema/performance, deduplicate, sort by date."""
    # Filter out excluded categories
    filtered = []
    for e in events:
        cat = e.category.lower().strip()
        # Check each comma-separated sub-category
        if any(part.strip() in EXCLUDE_CATEGORIES for part in cat.split(",")):
            continue
        # Also check title for music/cinema keywords
        title_lower = e.title.lower()
        if any(w in title_lower for w in ["concert", "gig:", "dj set", "live band"]):
            continue
        # Skip kids/family/schools events
        if any(w in title_lower for w in [
            "family workshop", "design baby", "kids", "children",
            "toddler", "baby", "under 5", "school of", "schools live",
            "play after school", "sound explorers", "mini jam",
            "teacher drop-in", "ks1", "ks2", "eyfs",
        ]):
            continue
        # Skip livestream duplicates
        if "(livestream)" in title_lower:
            continue
        filtered.append(e)

    # Deduplicate by title+date
    seen = set()
    unique = []
    for e in filtered:
        key = (e.title.lower().strip(), e.start_date)
        if key not in seen:
            seen.add(key)
            unique.append(e)

    # Sort by date
    return sorted(unique, key=lambda e: (e.start_date or date.max, e.time or ""))


def normalize_category(cat: str) -> str:
    """Map raw categories to display categories for filtering."""
    cat_lower = cat.lower().strip()
    if any(w in cat_lower for w in ["talk", "lecture", "conversation", "panel", "discussion"]):
        return "Talks"
    if any(w in cat_lower for w in ["workshop", "class", "course", "drawing"]):
        return "Workshops"
    if any(w in cat_lower for w in ["opening", "private view", "exhibition"]):
        return "Openings"
    if any(w in cat_lower for w in ["network", "social", "meet", "supper"]):
        return "Social"
    if any(w in cat_lower for w in ["art", "visual", "design"]):
        return "Art & Design"
    return "Other"


CORE_VENUES = {
    "Barbican", "Design Museum", "Rich Mix", "ICA",
    "Wellcome Collection", "Photographers' Gallery", "Somerset House",
    "London Review Bookshop", "V&A",
}


def build_html(events):
    """Generate static HTML page with JS filtering."""
    OUTPUT.mkdir(exist_ok=True)

    # Add normalized category and source to each event for filtering
    for e in events:
        e._filter_cat = normalize_category(e.category)
        e._source = e.venue if e.venue in CORE_VENUES else "Eventbrite"

    # Source filter: only core venues + Eventbrite
    venue_order = [
        "Barbican", "Design Museum", "ICA", "Rich Mix",
        "Wellcome Collection", "Photographers' Gallery", "Somerset House",
        "London Review Bookshop", "V&A", "Eventbrite",
    ]
    sources = [v for v in venue_order if any(e._source == v for e in events)]

    categories = ["All", "Talks", "Workshops", "Openings", "Social", "Art & Design", "Other"]

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    template = env.get_template("page.html")
    html = template.render(
        events=events,
        sources=sources,
        categories=categories,
        updated_at=datetime.now().strftime("%-d %B %Y"),
    )
    (OUTPUT / "index.html").write_text(html)
    logging.info(f"Built {OUTPUT / 'index.html'}")


def build_email(events):
    """Generate email HTML."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    template = env.get_template("email.html")
    html = template.render(
        events=events[:40],  # Cap email at 40 events
        week_of=date.today().strftime("%-d %B %Y"),
        page_url=os.environ.get("PAGE_URL", ""),
    )
    return html


def send_email(html):
    """Send the digest email via Resend."""
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
        "subject": f"London Culture — Week of {date.today().strftime('%-d %b %Y')}",
        "html": html,
    })
    logging.info(f"Email sent to {to_email}")


def save_events(events):
    """Persist events to JSON."""
    DATA.mkdir(exist_ok=True)
    data = [
        {
            "title": e.title,
            "venue": e.venue,
            "url": e.url,
            "start_date": e.start_date.isoformat() if e.start_date else None,
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "time": e.time,
            "description": e.description,
            "category": e.category,
            "is_free": e.is_free,
            "area": e.area,
        }
        for e in events
    ]
    (DATA / "events.json").write_text(json.dumps(data, indent=2))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    all_events = scrape_simple()
    all_events.extend(scrape_browser())
    all_events = filter_events(all_events)

    logging.info(f"Total: {len(all_events)} events")

    save_events(all_events)
    build_html(all_events)

    if "--email" in sys.argv:
        html = build_email(all_events)
        send_email(html)


if __name__ == "__main__":
    main()
