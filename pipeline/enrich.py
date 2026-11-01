"""Stage 4 - resolve publisher URLs and take a one-line summary.

Google News RSS links are redirects (news.google.com/rss/articles/...). Resolving one
takes two requests: the article page gives a signature and timestamp, then Google's
batchexecute endpoint returns the publisher URL.

Thumbnail: the page's og:image (the preview image publishers set for link sharing),
read from the same request. The dashboard hotlinks it; some publishers block that.

Summary: the publisher's own standfirst (og:description / meta description), cut to
its first sentence. It is extractive, so nothing is invented. When the page is
paywalled, blocked or has no description, the summary falls back to the headline
and summary_source says so.

Results are stored in data/raw/enriched.jsonl (committed), keyed by guid, so each
article is resolved once, ever. Only canonical records (after dedup) are enriched.
"""
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .gnews import SESSION

STORE = Path(__file__).resolve().parent.parent / "data" / "raw" / "enriched.jsonl"
BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
WORKERS = 6


def resolve_url(gnews_url: str) -> str:
    page = SESSION.get(gnews_url.replace("/rss/articles/", "/articles/"), timeout=20).text
    gid = re.search(r'data-n-a-id="([^"]+)"', page)
    ts = re.search(r'data-n-a-ts="(\d+)"', page)
    sg = re.search(r'data-n-a-sg="([^"]+)"', page)
    if not (gid and ts and sg):
        return ""
    inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None,
                             None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
             gid[1], int(ts[1]), sg[1]]
    body = {"f.req": json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])}
    resp = SESSION.post(BATCH_URL, data=body, timeout=20)
    payload = json.loads(resp.text.split("\n\n", 1)[1])
    return json.loads(payload[0][2])[1]


def _meta(page: str, *names: str) -> str:
    for name in names:
        if m := re.search(rf'<meta[^>]+(?:property|name)="{name}"[^>]+content="([^"]*)"', page):
            return html.unescape(m[1]).strip()
    return ""


def page_details(url: str) -> tuple[str, str]:
    """(standfirst, image_url) from the publisher page's Open Graph tags."""
    page = SESSION.get(url, timeout=20).text[:200_000]
    image = _meta(page, "og:image", "twitter:image")
    text = _meta(page, "og:description", "description")
    if not text:
        return "", image
    text = re.sub(r"^[A-Z][A-Z .,/]{2,40}:\s*", "", text)  # drop dateline, e.g. "HYDERABAD: "
    first = re.split(r"(?<=[.!?])\s+", text)[0]
    if len(first) > 280:
        first = first[:280].rsplit(" ", 1)[0]
    if not first.endswith((".", "!", "?", "…")):  # publishers often truncate their own tags
        first += "…"
    return first, image


def _enrich_one(rec: dict) -> dict:
    out = {"guid": rec["guid"], "publisher_url": "", "summary": "", "summary_source": "headline",
           "image_url": ""}
    try:
        out["publisher_url"] = resolve_url(rec["gnews_url"])
        if out["publisher_url"]:
            summary, out["image_url"] = page_details(out["publisher_url"])
            if summary:
                out["summary"], out["summary_source"] = summary, "publisher standfirst"
    except Exception as e:  # one bad page must not stop the run; recorded per record
        out["error"] = type(e).__name__
    return out


def load_store() -> dict[str, dict]:
    if not STORE.exists():
        return {}
    with open(STORE, encoding="utf-8") as f:
        return {r["guid"]: r for r in map(json.loads, f)}


def enrich(records: list[dict]) -> dict[str, dict]:
    store = load_store()
    todo = [r for r in records if r["guid"] not in store]
    print(f"enrich: {len(records) - len(todo)} cached, {len(todo)} to fetch")
    with ThreadPoolExecutor(WORKERS) as pool, open(STORE, "a", encoding="utf-8") as f:
        for i, res in enumerate(pool.map(_enrich_one, todo), 1):
            store[res["guid"]] = res
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}")
    return store
