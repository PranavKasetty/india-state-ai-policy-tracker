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
article is resolved once, ever. Only canonical records (after dedup) are enriched,
newest first, a capped number per run (Google throttles link resolving).
"""
import html
import json
import re
import time
from pathlib import Path

import requests

from .gnews import SESSION

STORE = Path(__file__).resolve().parent.parent / "data" / "raw" / "enriched.jsonl"
BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
DELAY_SECONDS = 1.0
MAX_FAILS = 5


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


META_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?\s*([\w.:-]+)""", re.I)
GARBLED_RUN = re.compile(r"[Â-ô][\u0080-¿]+")


def page_text(resp: requests.Response) -> str:
    """Decode a page with the charset it declares (header, then <meta>), else UTF-8.

    requests falls back to ISO-8859-1 when the Content-Type header has no charset,
    which turns UTF-8 punctuation into mojibake ("’" -> "â\x80\x99")."""
    if "charset" not in resp.headers.get("content-type", "").lower():
        m = META_CHARSET.search(resp.content[:4096])
        resp.encoding = m[1].decode("ascii") if m else "utf-8"
    return resp.text  # an unknown charset name falls back to replacing bad bytes


def repair_mojibake(text: str) -> str:
    """Undo UTF-8 that was decoded as Latin-1, one run at a time (stored summaries
    mix such runs with real non-Latin-1 text, e.g. the "…" added on truncation).
    A run that does not decode cleanly as UTF-8 is left alone."""
    def fix(m: re.Match) -> str:
        try:
            return m[0].encode("latin-1").decode("utf-8")
        except UnicodeError:
            return m[0]
    return GARBLED_RUN.sub(fix, text)


def page_details(url: str) -> tuple[str, str]:
    """(standfirst, image_url) from the publisher page's Open Graph tags."""
    page = page_text(SESSION.get(url, timeout=20))[:200_000]
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


def _enrich_one(rec: dict) -> dict | None:
    """None when Google refuses (throttling): not stored, so a later run retries it.
    A publisher page that fails is stored with the headline fallback: paywalls and
    bot blocks tend to be permanent."""
    try:
        url = resolve_url(rec["gnews_url"])
    except requests.RequestException:
        return None
    if not url:
        return None
    out = {"guid": rec["guid"], "publisher_url": url, "summary": "", "summary_source": "headline",
           "image_url": ""}
    try:
        summary, out["image_url"] = page_details(url)
        if summary:
            out["summary"], out["summary_source"] = summary, "publisher standfirst"
    except requests.RequestException as e:
        out["error"] = type(e).__name__
    return out


def load_store() -> dict[str, dict]:
    if not STORE.exists():
        return {}
    with open(STORE, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    for r in rows:  # summaries stored before page_text decoded pages properly
        if r.get("summary"):
            r["summary"] = repair_mojibake(r["summary"])
    return {r["guid"]: r for r in rows}


def enrich(records: list[dict], limit: int) -> dict[str, dict]:
    """Enrich up to `limit` un-enriched records, newest first. Google throttles link
    resolving, so this runs sequentially and stops after MAX_FAILS refusals in a row;
    the rest are picked up by later (daily) runs."""
    store = load_store()
    todo = sorted((r for r in records if r["guid"] not in store), key=lambda r: r["date"], reverse=True)
    print(f"enrich: {len(records) - len(todo)} done, {len(todo)} pending, fetching up to {limit}")
    fails = done = 0
    with open(STORE, "a", encoding="utf-8") as f:
        for rec in todo[:limit]:
            res = _enrich_one(rec)
            time.sleep(DELAY_SECONDS)
            if res is None:
                fails += 1
                if fails >= MAX_FAILS:
                    print(f"  stopping: Google refused {MAX_FAILS} requests in a row")
                    break
                continue
            fails, done = 0, done + 1
            store[res["guid"]] = res
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            f.flush()
            if done % 50 == 0:
                print(f"  {done} enriched")
    print(f"enrich: {done} new this run")
    return store
