# London Culture

Weekly aggregator of creative social events in London. Static page + email digest for a friend (mid-40s, East London) who wants to meet interesting people at talks, openings, workshops — not sit alone in a cinema.

## What This Is

Python scraper that pulls events from 10 sources, filters out music/cinema/kids stuff, generates a static HTML page with JS filter tabs, and optionally emails a weekly digest via Resend. Deployed via GitHub Pages + Actions cron (Monday 9am UTC).

## Key Principle

**Social events only.** No exhibitions (solitary), no music/cinema/performance (not social), no kids/family events. We want: talks, gallery openings, workshops (life drawing, ceramics, printmaking), creative networking, supper clubs, book launches, Friday Lates.

## Sources (10)

### Simple scrapers (requests + BeautifulSoup):
1. **Rich Mix** — `/whats-on/this-week` + `/whats-on/next-week`, `div.tease` elements
2. **Eventbrite** — 8 search terms (life-drawing, gallery-opening, creative-networking, etc.), extracts `window.__SERVER_DATA__` JSON
3. **Barbican** — `/whats-on/talks-events` (NOT main whats-on), `article.listing--event`
4. **Design Museum** — `/whats-on/talks-courses-and-workshops` (NOT `/exhibitions`)
5. **Wellcome Collection** — Public REST API at `api.wellcomecollection.org/content/v0/events`, no auth needed. All events free.
6. **Photographers' Gallery** — `/whats-on`, `article.o-event` elements, Drupal pagination
7. **Somerset House** — `/whats-on`, embedded JSON in `<script id="props" type="application/json">`. Needs JSON escape fixing (`\!` etc.)
8. **London Review Bookshop** — `/events`, links to Eventbrite with `h2.event-preview--title` + `span.event-preview--date`
9. **V&A** — `/whatson`, two card layouts: `b-events-featured__*` and `b-event-teaser__*`. 135+ event links, heavy dedup needed.

### Browser scraper (Playwright):
10. **ICA** — `/talks` (NOT `/whats-on` which is just a landing page). Fully JS-rendered, needs `domcontentloaded` + 5s wait. Title has `<br>` between prefix (WORKSHOP, BOOK LAUNCH) and actual title.

### Can't scrape:
- **Southbank Centre** — Cloudflare "Just a moment..." challenge blocks even Playwright headless.

## Filtering

### Global filters (in `scrape.py`):
- **Category exclusion**: music, cinema, film, gigs, live events, classical music, contemporary music, performing & visual arts. Checks comma-separated sub-categories.
- **Title exclusion**: concert, gig:, dj set, live band, family workshop, design baby, kids, children, toddler, baby, school of, schools live, ks1, ks2, eyfs, (livestream)
- **Dedup**: by (title.lower(), start_date)
- **Sort**: chronological by date, then time

### Per-scraper filters:
- Rich Mix: skips families/kids/music/cinema/gigs categories
- Eventbrite: skips online events, non-London events (LONDON_AREAS set), kids/family titles
- ICA: skips film screenings, ongoing programmes (multi-month date ranges)
- V&A: only includes talk, drop-in, special event, workshop, late, performance types
- Photographers' Gallery: only includes Talks & Events, Workshops & Courses, Bookshop Event, Tours
- Somerset House: only includes talk, workshop, late-night, event, relaxed-session, access-event types

## Page UI

- Chronological date headers ("Friday 14 February")
- Two filter rows: **Type** (All/Talks/Workshops/Openings/Social/Art & Design/Other) and **Source** (core venues + Eventbrite)
- Source filter buckets: Eventbrite misc venues all show as "Eventbrite", core venues keep their name
- Vanilla JS filtering, no framework
- System fonts, 720px max-width, mobile-friendly

## File Structure

```
scrape.py                          # Entry point: scrape → filter → build HTML/email
scrapers/
  base.py                          # Event dataclass + BaseScraper (1s delay, honest UA)
  rich_mix.py, eventbrite.py, barbican.py, design_museum.py
  wellcome.py, photographers_gallery.py, somerset_house.py
  lrb_bookshop.py, vam.py, ica.py
templates/
  page.html                        # Static page with JS filter tabs
  email.html                       # Inline-styled email digest (capped at 40 events)
output/index.html                  # Generated, served by GitHub Pages
data/events.json                   # Persisted for future diff detection
.github/workflows/scrape.yml      # Monday 9am UTC cron + manual trigger
requirements.txt                   # requests, beautifulsoup4, jinja2, resend, playwright
```

## Running

```bash
python scrape.py              # Scrape all, build page
python scrape.py --email      # Also send digest (needs RESEND_API_KEY + DIGEST_EMAIL)
```

## Repo

https://github.com/b1rdmania/london-culture

## Remaining TODO

- [x] Git init + first commit
- [x] Create GitHub repo + push
- [x] Enable GitHub Pages on gh-pages branch → **https://b1rdmania.github.io/london-culture/**
- [x] Test GitHub Actions workflow end-to-end (manual trigger via workflow_dispatch)
- [ ] Configure Resend: set `RESEND_API_KEY`, `DIGEST_EMAIL`, `PAGE_URL` as repo secrets
- [ ] Send friend the bookmark URL
- [ ] Consider: "New this week" detection via events.json diffing
- [ ] Consider: RSS feed output
- [ ] Consider: monitoring alerts if a venue returns 0 events
