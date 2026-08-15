"""Taste scoring for events via the Anthropic API. Scores are cached by URL
in events.json, so only new events cost anything. Skips without a key."""
import json
import logging
import os
from pathlib import Path

import requests

ROOT = Path(__file__).parent
MODEL = os.environ.get("SCORE_MODEL", "claude-sonnet-5")
BATCH = 40
TAGS = ["ideas", "creative-tech", "art", "writing", "making", "social", "generic"]


def _key():
    k = os.environ.get("ANTHROPIC_API_KEY")
    if not k:
        p = Path.home() / ".anthropic-key"
        if p.exists():
            k = p.read_text().strip()
    return k


def score_events(events, prev_rows):
    """Attach _score, _why, _mixed, _tag to events. prev_rows: previous events.json."""
    cache = {r["url"]: r for r in prev_rows if r.get("url") and r.get("score") is not None}
    todo = []
    for e in events:
        c = cache.get(e.url)
        if c:
            e._score, e._why, e._mixed, e._tag = c["score"], c.get("why", ""), bool(c.get("mixed")), c.get("tag", "")
        else:
            e._score, e._why, e._mixed, e._tag = None, "", False, ""
            todo.append(e)
    key = _key()
    if not key:
        logging.warning("No ANTHROPIC_API_KEY (or ~/.anthropic-key) — %d events left unscored", len(todo))
        return
    taste = (ROOT / "TASTE.md").read_text()
    logging.info("Scoring %d new events with %s", len(todo), MODEL)
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        try:
            _score_batch(batch, taste, key)
        except Exception as ex:
            logging.error("Scoring batch failed: %s", ex)


def _score_batch(batch, taste, key):
    items = [
        {"i": n, "title": e.title, "venue": e.venue, "source": e.source,
         "when": f"{e.start_date} {e.time}", "desc": (e.description or "")[:200]}
        for n, e in enumerate(batch)
    ]
    prompt = (
        f"{taste}\n\n---\nScore each event for this person. Return ONLY a JSON array, "
        f"one object per event, same order, keys: i, score (0-10 int), why (<=10 words, "
        f"plain, no hype), mixed (true if a mixed social crowd is likely), tag (one of {TAGS}).\n\n"
        f"Events:\n{json.dumps(items, ensure_ascii=False)}"
    )
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 4000, "temperature": 0.2,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=180,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"]).strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text[4:] if text.startswith("json") else text
    rows = json.loads(text)
    for row in rows:
        try:
            e = batch[int(row["i"])]
        except (KeyError, ValueError, IndexError):
            continue
        e._score = max(0, min(10, int(row.get("score", 0))))
        e._why = str(row.get("why", ""))[:80]
        e._mixed = bool(row.get("mixed"))
        e._tag = row.get("tag") if row.get("tag") in TAGS else ""
