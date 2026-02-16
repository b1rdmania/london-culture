import json
from datetime import date, datetime

from .base import BaseScraper, Event


class WellcomeScraper(BaseScraper):
    name = "Wellcome Collection"
    base_url = "https://api.wellcomecollection.org/content/v0"

    def scrape(self) -> list[Event]:
        events = []
        try:
            import time
            time.sleep(1)
            url = (
                f"{self.base_url}/events"
                "?format=%21exhibitions"
                "&timespan=future"
                "&sort=times.startDateTime"
                "&sortOrder=asc"
                "&pageSize=25"
            )
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                title = item.get("title", "")
                uid = item.get("uid", "")
                if not title or not uid:
                    continue

                # Format/category
                fmt = item.get("format", {})
                fmt_label = fmt.get("label", "") if fmt else ""

                # First future time
                start_date = None
                time_str = ""
                for t in item.get("times", []):
                    start_str = t.get("startDateTime", "")
                    if start_str:
                        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        if dt.date() >= date.today():
                            start_date = dt.date()
                            time_str = dt.strftime("%-I:%M%p").lower()
                            break

                if not start_date:
                    continue

                event_url = f"https://wellcomecollection.org/events/{uid}"

                # Description from promo text
                promo = item.get("promo", {})
                description = promo.get("caption", "") if promo else ""

                events.append(Event(
                    title=title,
                    venue=self.name,
                    url=event_url,
                    start_date=start_date,
                    time=time_str,
                    category=fmt_label,
                    is_free=True,  # Wellcome events are almost all free
                    area="Euston",
                    description=description,
                ))

        except Exception as e:
            self.logger.error(f"Wellcome scrape failed: {e}")
        return events
