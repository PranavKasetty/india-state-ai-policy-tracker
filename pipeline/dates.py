"""Date normalisation.

Every record gets an ISO date at its known precision plus a `date_precision` flag:
  day     "2026-07-30"
  month   "2026-07"
  year    "2026"
  unknown ""
Reduced-precision ISO strings still sort correctly, and nothing is invented: a
month-only date is never padded to the 1st.

RSS pubDates are in UTC. India is UTC+5:30 with no daylight saving, so we convert
before taking the date: a story stamped 20:00 UTC was published the next day in India.
The date is the *report* date (first publication), not the date of the event itself.
"""
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

IST = timezone(timedelta(hours=5, minutes=30))
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def normalize_date(raw: str | None) -> tuple[str, str]:
    """Return (iso_date, precision) for an RSS pubDate, ISO string or loose text."""
    raw = (raw or "").strip()
    if not raw:
        return "", "unknown"
    try:  # RFC 822, as used by RSS: "Thu, 30 Jul 2026 07:00:00 GMT"
        return parsedate_to_datetime(raw).astimezone(IST).date().isoformat(), "day"
    except (TypeError, ValueError):
        pass
    try:  # ISO 8601, with or without time
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone(IST)
        return dt.date().isoformat(), "day"
    except ValueError:
        pass
    if m := re.fullmatch(r"(\d{4})-(\d{2})", raw):
        return f"{m[1]}-{m[2]}", "month"
    if m := re.search(r"([A-Za-z]{3})[a-z]*\.?,? (\d{4})", raw):  # "July 2026"
        if (mon := _MONTHS.get(m[1].lower())):
            return f"{m[2]}-{mon:02d}", "month"
    if m := re.fullmatch(r"(\d{4})", raw):
        return m[1], "year"
    return "", "unknown"
