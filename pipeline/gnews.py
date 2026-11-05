"""Google News RSS search: fetch, cache, parse.

Why Google News RSS: free, no API key, indexes most Indian English outlets, supports
date-bounded search (after:/before:), so anyone can rerun the pipeline.
Limits: no pagination and a truncated result set per query (we work around it by
searching narrow date windows, see search_range), headline + outlet only (no article
text), and links are Google redirect URLs.

Every response is cached under data/cache/gnews/ keyed by the query URL, so reruns
are offline and reproducible. Delete the cache to refetch.
"""
import hashlib
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "gnews"
BASE = "https://news.google.com/rss/search"
DELAY_SECONDS = 0.75  # politeness delay between live requests

# Retry only transient failures: connection errors, timeouts, 429 (honouring
# Retry-After) and 5xx, with exponential backoff (2s, 4s, 8s, 16s). Other errors,
# e.g. 400 for a malformed query, fail immediately.
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (research project; Indian state AI policy tracker)"
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
    respect_retry_after_header=True)))


def search_url(query: str) -> str:
    params = {"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
    return BASE + "?" + urllib.parse.urlencode(params)


def fetch(query: str, refresh: bool = False) -> bytes:
    """Return raw RSS XML for a query, from cache when available."""
    return fetch_url(search_url(query), refresh)


def fetch_url(url: str, refresh: bool = False) -> bytes:
    """Return raw RSS XML for a search URL (any language edition), from cache when available."""
    path = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".xml")
    if path.exists() and not refresh:
        return path.read_bytes()
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()  # anything still failing after retries is a real error
    body = resp.content
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    time.sleep(DELAY_SECONDS)
    return body


def parse(xml_bytes: bytes) -> Iterator[dict[str, str]]:
    """Yield one dict per RSS item. Fields are raw strings; normalisation happens later."""
    root = ET.fromstring(xml_bytes)
    for item in root.iter("item"):
        source = item.find("source")
        source_name = source.text.strip() if source is not None and source.text else ""
        title = (item.findtext("title") or "").strip()
        # Google appends " - Outlet Name" to every headline; strip it.
        if source_name and title.endswith(" - " + source_name):
            title = title[: -len(" - " + source_name)].strip()
        yield {
            "title": title,
            "gnews_url": (item.findtext("link") or "").strip(),
            "guid": (item.findtext("guid") or "").strip(),
            "published_raw": (item.findtext("pubDate") or "").strip(),
            "source_name": source_name,
            "source_homepage": source.get("url", "") if source is not None else "",
        }


def search(query: str, refresh: bool = False) -> list[dict[str, str]]:
    return list(parse(fetch(query, refresh=refresh)))


def date_windows(start: date, end: date, days: int) -> Iterator[tuple[date, date]]:
    """Split [start, end) into consecutive windows of `days` days."""
    while start < end:
        stop = min(start + timedelta(days=days), end)
        yield start, stop
        start = stop


def search_range(query: str, start: date, end: date, days: int) -> list[dict[str, str]]:
    """Search [start, end) in windows of `days` days, merging results by guid.

    RSS has no pagination and returns a relevance-truncated subset per query, so
    narrower date windows recover more items (measured: one quarter 31 items,
    the same quarter by month 106).
    """
    items: dict[str, dict[str, str]] = {}
    for a, b in date_windows(start, end, days):
        try:
            found = search(f"{query} after:{a} before:{b}")
        except requests.HTTPError as e:  # Google occasionally 404s one window; skip it, not the run
            print(f"  skipped window {a}..{b}: {e.response.status_code}")
            continue
        except requests.RequestException as e:  # e.g. a read timeout mid-response, which is not retried;
            print(f"  skipped window {a}..{b}: {type(e).__name__}")  # uncached, so a rerun fills it
            continue
        for it in found:
            items.setdefault(it["guid"], it)
    return list(items.values())
