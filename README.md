# London Culture

**A daily list of things in London worth leaving the house for.**

Talks, gallery openings, workshops, book launches, tech meetups, politics and ideas — events where you meet people, not sit alone in a cinema.

## What's Included

- **Talks & workshops** — Barbican, ICA, Design Museum, Wellcome Collection, V&A, Somerset House
- **Politics & ideas** — Conway Hall, How To Academy, Gresham College, Bishopsgate Institute
- **Galleries** — Photographers' Gallery, Whitechapel Gallery, Rich Mix
- **Writing** — London Review Bookshop, Poetry Society
- **Tech** — Luma, Meetup
- **Everything social** — Eventbrite searches (life drawing, supper clubs, private views, book launches, debates…)

## What's Excluded

- Music/cinema/performance (not social)
- Exhibitions (solitary viewing)
- Kids/family events

## How It Works

The page updates **daily at 06:00 UTC**. Filter by when (today / next 7 days / weekend), interest (Talks, Politics & Ideas, Tech, Writing, Openings, Workshops, Social), and toggle **new this week** or **free**. Filters persist in the URL hash.

## View the Page

**→ [b1rdmania.github.io/london-culture](https://b1rdmania.github.io/london-culture/)**

---

## Technical Details

Python scraper (requests + BeautifulSoup, Playwright fallback for sites that block datacenter IPs or render with JS), deployed via GitHub Actions to GitHub Pages. `output/events.json` and `output/health.json` are published alongside the page; the next run reads `events.json` back to work out what's new.

See `CLAUDE.md` for implementation details.
