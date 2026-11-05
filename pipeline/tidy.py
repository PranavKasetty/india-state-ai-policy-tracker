"""Clean up what publishers' pages give us, before it is shown.

Applied when records are built (pipeline/run.py), so stored enrichment is fixed
without fetching pages again:

- summaries: drop a dateline ("Patna:", "Mumbai, Oct 9:"), drop a summary cut at an
  abbreviation ("Odisha Governor Dr.") or one that is the site's own description
  rather than the article's ("Get latest Mumbai news headlines...");
- thumbnails: drop an outlet's stock image (logo, emblem, default picture), found by
  its name or by the same image appearing on several records from one outlet.
"""
import re
from collections import Counter

# Abbreviations that end in a full stop without ending the sentence, and initials
# ("S.", "L.D.", "C.V.").
ABBREVIATION = re.compile(
    r"(?:\b(?:Dr|Sh|Shri|Smt|Mr|Mrs|Ms|Prof|Hon|St|No|Nos|Govt|Dept|Lt|Col|Gen|Capt|Maj|Ltd|Inc|Co|"
    r"Jr|Sr|vs|Rs|Gov|Sen|Rep|Fig|Vol|Art|Sec|approx|est)|\b(?!I\.$)[A-Z](?:\.[A-Z])*)\.$")  # not "Phase I."
# A dateline is place names and an optional date, every word capitalised:
# "Patna", "Chennai, 24th of October, 2026", "Daijiworld Media Network - Mumbai".
DATELINE = re.compile(r"^([^:\"“”']{2,60}?)\s*:\s+")
DATELINE_WORD = re.compile(r"^(?:[A-Z0-9(\[][\w.()\[\]/&-]*|of|and|the|-|–|—|,)$")
# Matched against the file name only: some outlets keep article photos under /logo/ or /default/.
STOCK_IMAGE = re.compile(r"logo|default|placeholder|emblem|og-image|fallback|no-?image", re.I)
SITE_BLURB = re.compile(r"latest (?:\w+ )?news|breaking news|news headlines|top stories|your description|"
                        r"read more|click here|subscribe to", re.I)
STOCK_REPEATS = 3  # the same image on this many records from one outlet is a stock image


def first_sentence(text: str) -> str:
    """The first sentence, not stopping at abbreviations or initials."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    out = parts[0]
    for part in parts[1:]:
        if not ABBREVIATION.search(out):
            break
        out += " " + part
    return out


def strip_dateline(text: str) -> str:
    m = DATELINE.match(text)
    if m and all(DATELINE_WORD.match(w) for w in m[1].replace(",", " , ").split()):
        return text[m.end():]
    return text


def clean_summary(summary: str) -> str:
    """The summary fit to show, or "" when it is cut short or about something else."""
    if not summary:
        return ""
    text = strip_dateline(summary.strip())
    if ABBREVIATION.search(text.rstrip("…").rstrip()):  # cut at "Dr." when it was stored
        return ""
    if SITE_BLURB.search(text):  # the site's description, not the article's
        return ""
    return text


def stock_images(records: list[dict]) -> set[str]:
    """Image URLs that are an outlet's stock picture rather than the article's."""
    per_outlet = Counter((r["source_name"], r["image_url"]) for r in records if r.get("image_url"))
    repeated = {img for (_, img), n in per_outlet.items() if n >= STOCK_REPEATS}
    named = {r["image_url"] for r in records
             if r.get("image_url") and STOCK_IMAGE.search(r["image_url"].split("?")[0].rsplit("/", 1)[-1])}
    return repeated | named
