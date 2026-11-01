"""Stage 6 (optional, needs an LLM key) - short briefs per state and per category.

Each brief is 3-4 sentences written by the LLM from that group's records only (the
MAX_RECORDS most-covered, then most recent), and must cite record IDs for every
claim. Cited IDs are checked against the input: unknown IDs are dropped, and a brief
with no valid citation is discarded. Briefs are stored in data/output/briefs.json with
a hash of their input, and regenerated only when that input changes.
"""
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from . import llm
from .classify import CATEGORY_IDS

STORE = Path(__file__).resolve().parent.parent / "data" / "output" / "briefs.json"
MAX_RECORDS = 60
MIN_RECORDS = 10  # no brief for a group with fewer records than this

PROMPT = """You write short, neutral briefs for a dataset of AI policy activity by Indian
state governments (Nov 2025 onwards). Use ONLY the records given; do not add facts,
numbers or context that are not in them. Write 3-4 sentences on the main themes and the
most significant actions. After each sentence, cite the record IDs it relies on in square
brackets, e.g. [R1a2b3c4d, R5e6f7a8b]. Return JSON: {"brief": "<text with citations>"}"""


def _lines(records: list[dict]) -> list[str]:
    top = _top(records, MAX_RECORDS)
    return [f"{r['record_id']} | {r['date']} | {r['state']} | {r['title']} - {r['summary']}" for r in top]


def _top(records: list[dict], k: int) -> list[dict]:
    """The k most-covered records, most recent first among equals."""
    by_date = sorted(records, key=lambda r: r["date"] or "", reverse=True)
    return sorted(by_date, key=lambda r: -r["n_sources"])[:k]  # stable sort keeps date order


def _groups(records: list[dict]) -> dict[str, tuple[str, list[dict]]]:
    """key -> (subject phrase for the prompt, records)."""
    groups = {}
    states = sorted({r["state"] for r in records})
    # Overall: the top K per state, so the largest states don't fill the whole input.
    k = MAX_RECORDS // max(len(states), 1)
    groups["overall"] = ("AI policy activity across all covered Indian states",
                         [r for st in states for r in _top([r for r in records if r["state"] == st], k)])
    for state in states:
        members = [r for r in records if r["state"] == state]
        if len(members) >= MIN_RECORDS:
            groups[f"state:{state}"] = (f"the state of {state}", members)
    for label, cid in CATEGORY_IDS.items():
        members = [r for r in records if label in r["tags"]]
        if len(members) >= MIN_RECORDS and cid != "other":
            groups[f"category:{cid}"] = (f"'{label}' activity across states", members)
    return groups


def build(records: list[dict]) -> dict[str, dict]:
    store = json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}
    key, model, base = llm.config()
    if not key:
        print("briefs: no API key, keeping stored briefs")
        return store
    session = llm.make_session(key)
    made = 0
    for gkey, (subject, members) in _groups(records).items():
        lines = _lines(members)
        digest = hashlib.sha1("\n".join(lines).encode()).hexdigest()[:12]
        if store.get(gkey, {}).get("input_hash") == digest:
            continue
        try:
            text = llm.chat_json(session, base, model, PROMPT,
                                 f"Brief on {subject}.\nRecords:\n" + "\n".join(lines))["brief"]
        except Exception as e:  # keep the previous brief rather than fail the run
            print(f"  {gkey}: failed ({type(e).__name__})")
            continue
        valid = {ln.split(" | ")[0] for ln in lines}
        cited = [c for c in re.findall(r"R[0-9a-f]{8}", text) if c in valid]
        text = re.sub(r"R[0-9a-f]{8}", lambda m: m[0] if m[0] in valid else "", text)
        text = re.sub(r"\[\s*(,\s*)*\]", "", re.sub(r",\s*(?=[,\]])|(?<=\[)\s*,\s*", "", text))
        if not cited:
            print(f"  {gkey}: no valid citations, discarded")
            continue
        store[gkey] = {"text": text.strip(), "cited": list(dict.fromkeys(cited)), "n_records": len(members),
                       "model": model, "input_hash": digest,
                       "generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes")}
        made += 1
        time.sleep(4.5)  # free-tier requests per minute
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"briefs: {made} generated, {len(store)} stored")
    return store
