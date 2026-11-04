"""Regional-language news: Hindi for the Hindi-speaking states, Marathi for Maharashtra.

Why these: a one-month probe in 12 languages (analysis/regional/README.md) found that
English coverage misses about half of UP's AI developments, most of MP's and
Rajasthan's, and a good share of Maharashtra's, mostly department- and district-level
implementation. Other languages added little (Kerala, Tamil Nadu, Telugu states,
Punjab), and Google News has no Kannada or Odia edition.

Flow, kept apart from the English stages so their inputs and caches do not change:
  collect   Google News in the language's edition: (AI terms) (state names in script),
            weekly windows. Stored in data/raw/items_regional.jsonl.
  filter    an AI or robotics term must appear in the original headline (Google's
            regional search matches loosely; without this a third of items had none).
  label     the LLM applies the same rubric (llm.RUBRIC) to the original headline and
            also returns an English translation and the state it is about. Cached in
            data/raw/llm_labels_regional.jsonl by guid and prompt version.
  records   in-scope items about the state that was searched become candidates in the
            same shape as English ones, titled with the translation, so deduplication
            (TF-IDF, then the LLM pair check) merges them with English reports of the
            same development.

A run labels at most MAX_BATCHES batches, so the 12-month backfill spreads over a few
runs instead of using up the free LLM quota in one.
"""
import json
import re
import time
import urllib.parse
from datetime import date
from pathlib import Path

import requests

from . import gnews, llm
from .classify import CATEGORY_LABELS, SECTORS
from .dates import normalize_date
from .states import state_code

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "raw" / "items_regional.jsonl"
LABELS = ROOT / "data" / "raw" / "llm_labels_regional.jsonl"
PROMPT_VERSION = "r1"
BATCH = 30            # smaller than English: each answer also carries a translation
MAX_BATCHES = 80      # per run; the backlog is picked up by later runs
WINDOW_DAYS = 7

LANGUAGES = {
    "hi": {"name": "Hindi", "ai": ["AI", "एआई", '"आर्टिफिशियल इंटेलिजेंस"', '"कृत्रिम बुद्धिमत्ता"'],
           "states": {"Uttar Pradesh": ['"उत्तर प्रदेश"', "यूपी"], "Bihar": ["बिहार"],
                      "Madhya Pradesh": ['"मध्य प्रदेश"', "एमपी"], "Rajasthan": ["राजस्थान"],
                      "Haryana": ["हरियाणा"], "Uttarakhand": ["उत्तराखंड"], "Himachal Pradesh": ["हिमाचल"],
                      "Jharkhand": ["झारखंड"], "Chhattisgarh": ["छत्तीसगढ़"]}},
    "mr": {"name": "Marathi", "ai": ["AI", "एआय", '"कृत्रिम बुद्धिमत्ता"'],
           "states": {"Maharashtra": ["महाराष्ट्र", '"राज्य सरकार"']}},
}
LANGUAGE_NAMES = {code: cfg["name"] for code, cfg in LANGUAGES.items()}

# An AI or robotics term in the original headline (the English pipeline's "no AI term" rule).
AI_TERM = re.compile(r"\bAI\b|A\.I\.|एआई|एआय|आर्टिफिशियल|कृत्रिम बुद्धि|रोबोट|robot|चैटबॉट|चॅटबॉट", re.I)
LATIN = re.compile(r"[A-Za-z]")
LETTER = re.compile(r"\w")


def search_url(query: str, lang: str) -> str:
    return gnews.BASE + "?" + urllib.parse.urlencode({"q": query, "hl": lang, "gl": "IN", "ceid": f"IN:{lang}"})


def load() -> dict[str, dict]:
    if not STORE.exists():
        return {}
    with open(STORE, encoding="utf-8") as f:
        return {r["guid"]: r for r in map(json.loads, f)}


def collect(start: date, end: date, window_days: int = WINDOW_DAYS, states: list[str] | None = None) -> int:
    """Search [start, end) in every language edition and merge into the store."""
    items = load()
    before = len(items)
    for lang, cfg in LANGUAGES.items():
        for state, names in cfg["states"].items():
            if states and state not in states:
                continue
            query = f"({' OR '.join(cfg['ai'])}) ({' OR '.join(names)})"
            n = 0
            for a, b in gnews.date_windows(start, end, window_days):
                try:
                    found = list(gnews.parse(gnews.fetch_url(search_url(f"{query} after:{a} before:{b}", lang))))
                except requests.HTTPError as e:
                    print(f"  skipped {state} {lang} {a}..{b}: {e.response.status_code}")
                    continue
                for it in found:
                    n += 1
                    items.setdefault(it["guid"], {**it, "lang": lang, "state_queried": state})
            print(f"{state:15} {lang}     {n:5} items")
    STORE.parent.mkdir(parents=True, exist_ok=True)
    with open(STORE, "w", encoding="utf-8") as f:
        for row in items.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"regional collect: {len(items) - before} new, {len(items)} total in {STORE.name}")
    return len(items) - before


def candidate(it: dict) -> bool:
    """Worth labelling: in the regional script (not an English headline in the regional
    edition, which the English collection covers) and naming an AI or robotics term."""
    letters = LETTER.findall(it["title"])
    if not letters or len(LATIN.findall(it["title"])) / len(letters) > 0.5:
        return False
    return bool(AI_TERM.search(it["title"]))


PROMPT = llm.RUBRIC.split("Return JSON")[0] + """The headlines are in Hindi or Marathi. Apply the rubric to the original headline.
For every headline also give:
- "english": a faithful English translation of the headline, in news-headline style;
- "state": the Indian state the headline is about (English name), or null if none or unclear.
Return JSON: {"labels": [{"i": <number>, "in_scope": true|false, "english": "...", "state": "<state or null>",
"reason": "<max 12 words>", "primary": "<id or null>", "tags": [<ids>], "sector": "<sector or null>"}]} - one per headline."""


def load_labels() -> dict[str, dict]:
    if not LABELS.exists():
        return {}
    with open(LABELS, encoding="utf-8") as f:
        return {r["guid"]: r for r in map(json.loads, f) if r.get("prompt_version") == PROMPT_VERSION}


def label(items: list[dict], max_batches: int = MAX_BATCHES) -> dict[str, dict]:
    store = load_labels()
    todo = [it for it in items if it["guid"] not in store]
    key, model, base = llm.config()
    if not todo:
        return store
    if not key:
        print(f"regional: no API key, {len(todo)} headlines left unlabelled")
        return store
    todo = sorted(todo, key=lambda it: normalize_date(it["published_raw"])[0] or "", reverse=True)
    print(f"regional: {len(items) - len(todo)} cached, {len(todo)} to label with {model} "
          f"(up to {max_batches * BATCH} this run)")
    session = llm.make_session(key)
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    with open(LABELS, "a", encoding="utf-8") as f:
        for n, start in enumerate(range(0, len(todo), BATCH)):
            if n >= max_batches:
                print(f"  stopping at {max_batches} batches; {len(todo) - start} left for later runs")
                break
            batch = todo[start:start + BATCH]
            lines = "\n".join(f"{i}. {it['title']} ({it['source_name']})" for i, it in enumerate(batch))
            try:
                answers = llm._ask(session, base, model, PROMPT, lines, "labels")
            except (requests.RequestException, ValueError, KeyError, TypeError) as e:
                print(f"  batch {n} failed ({type(e).__name__}); retried next run")
                continue
            for a in answers:
                i = a.get("i")
                if not isinstance(i, int) or not 0 <= i < len(batch):
                    continue
                row = {"guid": batch[i]["guid"], "prompt_version": PROMPT_VERSION, "model": model,
                       **{k: a.get(k) for k in ("in_scope", "english", "state", "reason", "primary", "tags", "sector")}}
                store[row["guid"]] = row
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  {min(start + BATCH, len(todo))}/{len(todo)}")
            time.sleep(4.5)  # stay under 15 requests per minute
    return store


def classify(start_date: str, use_llm: bool, covered: list[str], sources_skip) -> tuple[list[dict], list[dict]]:
    """Regional candidates in the English candidates' shape, and the excluded ones.

    start_date: drop items before it (Google's after: filter is not strict).
    sources_skip(name) -> reason or "": the English pipeline's outlet rules.
    """
    items = [it for it in load().values() if candidate(it)]
    labels = label(items) if use_llm else load_labels()
    kept, excluded = [], []
    for it in items:
        iso, precision = normalize_date(it["published_raw"])
        lab = labels.get(it["guid"])
        state = it["state_queried"]
        base = {"guid": it["guid"], "title": (lab or {}).get("english") or it["title"], "title_original": it["title"],
                "language": it["lang"], "date": iso, "date_precision": precision, "source_name": it["source_name"],
                "gnews_url": it["gnews_url"], "state": state, "variants": ["regional"]}
        reason = sources_skip(it["source_name"])
        if not reason and iso and iso < start_date:
            reason = "dated before the tracking window"
        if not reason and not lab:
            reason = "regional: not yet labelled"
        if not reason and not lab.get("in_scope"):
            reason = f"llm: {lab.get('reason') or ''}"
        if not reason and lab.get("state") != state:
            reason = f"regional: about {lab.get('state') or 'no state'}, not {state}"
        if not reason and not lab.get("english"):
            reason = "regional: no translation"
        if reason or state not in covered:
            excluded.append({**base, "reason": reason or "state not covered", "classified_by": "llm" if lab else "rules"})
            continue
        tags = [CATEGORY_LABELS[t] for t in lab.get("tags") or [] if t in CATEGORY_LABELS]
        primary = CATEGORY_LABELS.get(lab.get("primary") or "", tags[0] if tags else "Other")
        sector = lab.get("sector") if lab.get("sector") in [*SECTORS, "Cross-cutting"] else "Cross-cutting"
        kept.append({**base, "state_code": state_code(state), "state_evidence": "regional query",
                     "primary_category": primary, "tags": list(dict.fromkeys([primary, *tags])),
                     "sector": sector, "classified_by": "llm"})
    print(f"regional: {len(items)} candidates, {len(kept)} in scope")
    return kept, excluded
