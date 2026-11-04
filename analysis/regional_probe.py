"""How much would regional-language news add? A one-month probe.

For 14 states, search Google News in the state's main language for October 2026
(state name + AI terms, weekly windows), then:
  1. the LLM applies the tracker's rubric to each regional headline, translates it,
     and says whether the actor is state-level or local (district, city, one office);
  2. for each in-scope regional item, the LLM looks for the same development among
     the English headlines the pipeline collected for that state (19 Sep - 4 Nov).

Outputs analysis/regional/items.csv (one row per regional headline) and prints a
summary. Google responses and LLM answers are cached, so reruns are offline.

Run:  python -m analysis.regional_probe
"""
import csv
import hashlib
import json
import re
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from pipeline import gnews, llm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "regional"
CACHE = ROOT / "data" / "cache" / "gnews_regional"
START, END = date(2026, 10, 1), date(2026, 11, 1)
EN_START, EN_END = date(2026, 9, 19), date(2026, 11, 4)

# state: (edition, state names in script, AI terms in script)
STATES = {
    "Uttar Pradesh": ("hi", ['"उत्तर प्रदेश"', "यूपी", "योगी"], ["एआई", '"आर्टिफिशियल इंटेलिजेंस"']),
    "Bihar": ("hi", ["बिहार"], ["एआई", '"आर्टिफिशियल इंटेलिजेंस"']),
    "Madhya Pradesh": ("hi", ['"मध्य प्रदेश"', "एमपी"], ["एआई", '"आर्टिफिशियल इंटेलिजेंस"']),
    "Rajasthan": ("hi", ["राजस्थान"], ["एआई", '"आर्टिफिशियल इंटेलिजेंस"']),
    "Telangana": ("te", ["తెలంగాణ"], ["ఏఐ", '"కృత్రిమ మేధ"']),
    "Andhra Pradesh": ("te", ['"ఆంధ్రప్రదేశ్"', "ఏపీ"], ["ఏఐ", '"కృత్రిమ మేధ"']),
    "Karnataka": ("kn", ["ಕರ್ನಾಟಕ", "ರಾಜ್ಯ"], ["ಎಐ", '"ಕೃತಕ ಬುದ್ಧಿಮತ್ತೆ"']),
    "Tamil Nadu": ("ta", ["தமிழ்நாடு", "தமிழக"], ["ஏஐ", '"செயற்கை நுண்ணறிவு"']),
    "Maharashtra": ("mr", ["महाराष्ट्र", "राज्य"], ["एआय", '"कृत्रिम बुद्धिमत्ता"']),
    "Kerala": ("ml", ["കേരള", "കേരളം"], ["എഐ", '"നിർമിത ബുദ്ധി"']),
    "Gujarat": ("gu", ["ગુજરાત"], ["એઆઈ", '"આર્ટિફિશિયલ ઇન્ટેલિજન્સ"']),
    "West Bengal": ("bn", ["পশ্চিমবঙ্গ", "রাজ্য"], ["এআই", '"কৃত্রিম বুদ্ধিমত্তা"']),
    "Odisha": ("or", ["ଓଡ଼ିଶା", "ଓଡିଶା"], ["ଏଆଇ", '"କୃତ୍ରିମ ବୁଦ୍ଧିମତ୍ତା"']),
    "Punjab": ("pa", ["ਪੰਜਾਬ"], ["ਏਆਈ", '"ਆਰਟੀਫਿਸ਼ੀਅਲ ਇੰਟੈਲੀਜੈਂਸ"']),
}
LATIN = re.compile(r"[A-Za-z]")
LETTER = re.compile(r"\w")


def fetch(query: str, lang: str) -> bytes:
    url = gnews.BASE + "?" + urllib.parse.urlencode({"q": query, "hl": lang, "gl": "IN", "ceid": f"IN:{lang}"})
    path = CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".xml")
    if path.exists():
        return path.read_bytes()
    resp = gnews.SESSION.get(url, timeout=30)
    resp.raise_for_status()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    time.sleep(1.0)
    return resp.content


def regional_items() -> list[dict]:
    rows = []
    for state, (lang, names, terms) in STATES.items():
        query = f"({' OR '.join(['AI', *terms])}) ({' OR '.join(names)})"
        seen = {}
        for a, b in gnews.date_windows(START, END, 7):
            for it in gnews.parse(fetch(f"{query} after:{a} before:{b}", lang)):
                seen.setdefault(it["guid"], it)
        kept = 0
        for it in seen.values():
            letters = LETTER.findall(it["title"])
            if not letters or len(LATIN.findall(it["title"])) / len(letters) > 0.5:
                continue  # an English headline in the regional edition
            try:
                day = parsedate_to_datetime(it["published_raw"]).astimezone(timezone(timedelta(hours=5, minutes=30))).date()
            except (TypeError, ValueError):
                continue
            if not START <= day < END:
                continue
            rows.append({"state": state, "lang": lang, "date": day.isoformat(), "title": it["title"],
                         "source": it["source_name"], "guid": it["guid"]})
            kept += 1
        print(f"{state}: {len(seen)} results, {kept} regional-language headlines in October")
    return rows


CLASSIFY = llm.RUBRIC.split("Return JSON")[0] + """
The headlines are in Indian languages (Hindi, Telugu, Kannada, Tamil, Marathi, Malayalam,
Gujarati, Bengali, Odia, Punjabi). Apply the rubric above to each one.
Also give:
- "english": a faithful English translation of the headline;
- "level": "state" when the actor is the state government itself (CM, minister, a state
  department, a statewide scheme or policy, a state agency), or "local" when it is a district,
  city, municipal body, police station, single school, hospital or university. null when OUT.
Return JSON: {"labels": [{"i": <number>, "in_scope": true|false, "english": "...",
"level": "state"|"local"|null, "primary": "<category id or null>"}]} - one per line."""

MATCH = """You compare news about an Indian state's AI activity across languages.
You get a list of REGIONAL items (translated to English) and a numbered list of ENGLISH
headlines from the same state and period. For each regional item, find the English headline
that reports the SAME development (same announcement, decision, launch, deployment or event),
not merely the same topic. Return JSON: {"matches": [{"i": <regional number>,
"en": <English number or null>}]} - one per regional item."""


def cached_llm(name: str, system: str, user: str, field: str, session, base, model) -> list:
    store = OUT / f"llm_{name}.jsonl"
    key = hashlib.sha1((system + user).encode()).hexdigest()
    if store.exists():
        for line in store.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["key"] == key:
                return row["answer"]
    answer = llm._ask(session, base, model, system, user, field)
    with open(store, "a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "answer": answer}, ensure_ascii=False) + "\n")
    time.sleep(4.5)
    return answer


def english_items() -> dict[str, list[dict]]:
    """English headlines the pipeline collected per state in the comparison window,
    marked with whether they made it into the dataset."""
    included = set()
    with open(ROOT / "data" / "output" / "sources.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            included.add(r.get("title", "").strip())
    by_state = defaultdict(dict)
    with open(ROOT / "data" / "raw" / "items.jsonl", encoding="utf-8") as f:
        for it in map(json.loads, f):
            try:
                day = parsedate_to_datetime(it["published_raw"]).date()
            except (TypeError, ValueError):
                continue
            if not EN_START <= day < EN_END:
                continue
            for s in it.get("states_queried", []):
                if s in STATES:
                    by_state[s].setdefault(it["title"], {"title": it["title"], "date": day.isoformat(),
                                                         "included": it["title"].strip() in included})
    return {s: sorted(v.values(), key=lambda x: x["date"]) for s, v in by_state.items()}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = regional_items()
    key, model, base = llm.config()
    if not key:
        sys.exit("needs LLM_API_KEY")
    session = llm.make_session(key)

    by_state = defaultdict(list)
    for r in rows:
        by_state[r["state"]].append(r)
    def classify(batch: list[dict]) -> None:
        """Label a batch; when the model's JSON is malformed, split it and try the halves."""
        lines = "\n".join(f"{i}. {it['title']} ({it['source']})" for i, it in enumerate(batch))
        try:
            labels = cached_llm("classify", CLASSIFY, lines, "labels", session, base, model)
        except (ValueError, KeyError, TypeError):
            if len(batch) <= 5:
                print(f"  skipped {len(batch)} headlines (malformed answers)")
                return
            half = len(batch) // 2
            classify(batch[:half])
            classify(batch[half:])
            return
        for lab in labels:
            if isinstance(lab.get("i"), int) and 0 <= lab["i"] < len(batch):
                batch[lab["i"]].update(in_scope=bool(lab.get("in_scope")), english=lab.get("english") or "",
                                       level=lab.get("level") or "", primary=lab.get("primary") or "")

    for state, items in by_state.items():
        for start in range(0, len(items), llm.BATCH):
            classify(items[start:start + llm.BATCH])

    english = english_items()
    for state, items in by_state.items():
        todo = [it for it in items if it.get("in_scope")]
        en = english.get(state, [])
        en_lines = "\n".join(f"{j}. [{e['date']}] {e['title']}" for j, e in enumerate(en))
        for start in range(0, len(todo), 25):
            batch = todo[start:start + 25]
            reg = "\n".join(f"{i}. [{it['date']}] {it['english']}" for i, it in enumerate(batch))
            user = f"REGIONAL:\n{reg}\n\nENGLISH:\n{en_lines}"
            try:
                matches = cached_llm("match", MATCH, user, "matches", session, base, model)
            except (ValueError, KeyError, TypeError):
                print(f"  {state}: a match batch failed (malformed answers); left unmatched")
                continue
            for m in matches:
                i, j = m.get("i"), m.get("en")
                if isinstance(i, int) and 0 <= i < len(batch):
                    hit = en[j] if isinstance(j, int) and 0 <= j < len(en) else None
                    batch[i]["english_match"] = hit["title"] if hit else ""
                    batch[i]["match_in_dataset"] = bool(hit and hit["included"])
        print(f"{state}: {len(en)} English headlines to compare, {len(todo)} in-scope regional")

    fields = ["state", "lang", "date", "title", "english", "source", "in_scope", "level", "primary",
              "english_match", "match_in_dataset", "guid"]
    with open(OUT / "items.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    summarise(rows)


# An AI or robotics term in the original headline, as the English pipeline requires.
# Google's regional search matches loosely; without this, a third of "in scope" items
# had no AI term at all.
AI_TERM = re.compile(r"\bAI\b|A\.I\.|एआई|एआय|आर्टिफिशियल|कृत्रिम|ఏఐ|కృత్రిమ|ஏஐ|செயற்கை|എഐ|നിർമി|എ\.ഐ|"
                     r"એઆઈ|આર્ટિફિશિયલ|এআই|কৃত্রিম|ਏਆਈ|ਏ\.ਆਈ|रोबोट|robot|రోబో|ரோபோ|റോബോ|রোবট|ਰੋਬੋਟ|"
                     r"ચેટબોટ|चैटबॉट|ड्रोन", re.I)


def summarise(rows: list[dict]) -> None:
    rows = [{**r, "in_scope": r.get("in_scope") in (True, "True") and bool(AI_TERM.search(r["title"])),
             "match_in_dataset": r.get("match_in_dataset") in (True, "True")} for r in rows]
    print("\nIn scope = judged in scope AND an AI term in the original headline")
    print("state | regional headlines | in scope | state-level | ...not in English collection | ...in English but not in dataset")
    tot = Counter()
    for state in STATES:
        rs = [r for r in rows if r["state"] == state]
        ins = [r for r in rs if r.get("in_scope")]
        st = [r for r in ins if r.get("level") == "state"]
        none = [r for r in st if not r.get("english_match")]
        excl = [r for r in st if r.get("english_match") and not r.get("match_in_dataset")]
        loc_none = [r for r in ins if r.get("level") == "local" and not r.get("english_match")]
        c = Counter(n=len(rs), ins=len(ins), st=len(st), none=len(none), excl=len(excl),
                    loc=len(ins) - len(st), loc_none=len(loc_none))
        tot += c
        print(f"{state} | {c['n']} | {c['ins']} | {c['st']} | {c['none']} | {c['excl']} | local {c['loc']} ({c['loc_none']} unmatched)")
    print(f"TOTAL | {tot['n']} | {tot['ins']} | {tot['st']} | {tot['none']} | {tot['excl']} | local {tot['loc']} ({tot['loc_none']} unmatched)")


if __name__ == "__main__":
    main()
