"""Stage 4 - resolve publisher URLs and take a one-line summary.

Google News RSS links are redirects (news.google.com/rss/articles/...). Resolving one
takes two requests: the article page gives a signature and timestamp, then Google's
batchexecute endpoint returns the publisher URL.

Thumbnail: the page's og:image (the preview image publishers set for link sharing),
read from the same request. The dashboard hotlinks it; some publishers block that.

Headline: Google News sometimes carries a headline cut short, usually because the
publisher's own <title> tag is cut ("...adopted at National e"). When the headline
looks cut (it ends in "..", or the article's URL slug carries on mid-word), the full
headline is taken from the article page and stored as full_title.

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

from collections import Counter
from urllib.parse import urlparse

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


ELLIPSIS = re.compile(r"\s*(\.{2,}|…)$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def looks_cut(title: str, url: str) -> bool:
    """True when the headline ends in an ellipsis, or the URL slug carries on with more
    words ("...-national-e" then "-governance-conference"). URLs without a slug say
    nothing. Slugs often add words of their own, so this only decides which pages to
    check; full_headline decides whether the headline was really cut."""
    if ELLIPSIS.search(title):
        return True
    head, path = _slug(title), _slug(urlparse(url).path)
    at = path.find(head)
    return len(head) > 20 and at >= 0 and re.match(r"-?[a-z]", path[at + len(head):]) is not None


def full_headline(page: str, title: str) -> str:
    """The page's longer version of a cut headline, or "" when the page has none.

    The page text is searched for the headline; what follows it, up to the end of that
    piece of text, is the missing part. Without an ellipsis, the continuation must go on
    mid-word, so a headline that merely starts a longer sentence is not extended."""
    stem = ELLIPSIS.sub("", title)
    cut_by_ellipsis = stem != title
    text = html.unescape(re.sub(r"<[^>]+>", "\n", page))
    found = Counter()
    for m in re.finditer(re.escape(stem), text):
        rest = re.match(r'[^\n|"\\]{1,200}', text[m.end():])  # stop at a tag, " | Outlet" or JSON
        if not rest:
            continue
        rest = rest[0].rstrip()
        if ELLIPSIS.search(rest):  # the page's copy is cut too
            continue
        if rest and (cut_by_ellipsis or re.match(r"[\w-]", rest)):
            found[rest] += 1
    if not found:
        return ""
    rest = max(found, key=lambda r: (found[r], -len(r)))  # most repeated, then shortest
    return stem + rest


def page_details(url: str, title: str = "") -> tuple[str, str, str]:
    """(standfirst, image_url, full_title) from the publisher page. full_title is ""
    unless the headline looks cut and the page has its full version."""
    page = page_text(SESSION.get(url, timeout=20))[:200_000]
    full = full_headline(page, title) if title and looks_cut(title, url) else ""
    image = _meta(page, "og:image", "twitter:image")
    text = _meta(page, "og:description", "description")
    if not text:
        return "", image, full
    text = re.sub(r"^[A-Z][A-Z .,/]{2,40}:\s*", "", text)  # drop dateline, e.g. "HYDERABAD: "
    first = re.split(r"(?<=[.!?])\s+", text)[0]
    if len(first) > 280:
        first = first[:280].rsplit(" ", 1)[0]
    if not first.endswith((".", "!", "?", "…")):  # publishers often truncate their own tags
        first += "…"
    return first, image, full


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
        summary, out["image_url"], out["full_title"] = page_details(
            url, rec["title"] if rec.get("language", "en") == "en" else "")
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
        retitle(records, store, f)
    print(f"enrich: {done} new this run")
    return store


def retitle(records: list[dict], store: dict[str, dict], f) -> None:
    """Records enriched before headlines were checked: fetch the page again for the few
    whose headline looks cut. Stored with full_title ("" when the page had none), so each
    is checked once."""
    todo = [r for r in records
            if r.get("language", "en") == "en" and r["guid"] in store and "full_title" not in store[r["guid"]]
            and store[r["guid"]].get("publisher_url") and looks_cut(r["title"], store[r["guid"]]["publisher_url"])]
    if todo:
        print(f"enrich: checking {len(todo)} headlines that look cut")
    for rec in todo:
        row = {**store[rec["guid"]], "full_title": ""}
        try:
            page = page_text(SESSION.get(row["publisher_url"], timeout=20))[:200_000]
            row["full_title"] = full_headline(page, rec["title"])
        except requests.RequestException:
            pass
        store[rec["guid"]] = row
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        time.sleep(DELAY_SECONDS)
