"""Stage 1 - collect: search Google News for every covered state, save raw items.

Three query variants per state:
  gov     "<State>" + AI terms + government terms   (precise)
  broad   "<State>" + AI terms                      (catches implied government action)
  agency  any state body from agencies.py + AI terms (stories that never name the state)
Each item records which variants and states found it, so we can report what each
variant contributed. Relevance is decided later, not here.

New items are merged into data/raw/items.jsonl (one JSON object per Google News item),
so the daily run only adds to the history.
"""
import json
from datetime import date
from pathlib import Path

from . import gnews
from .agencies import AGENCIES
from .terms import AI_QUERY, GOV_QUERY

COVERED_STATES = [
    "Karnataka", "Gujarat", "Kerala", "Maharashtra", "Tamil Nadu", "Telangana",
    "Uttar Pradesh", "Bihar", "Odisha", "Punjab", "Andhra Pradesh",
]
STORE = Path(__file__).resolve().parent.parent / "data" / "raw" / "items.jsonl"


def queries(state: str) -> list[tuple[str, str, int]]:
    """(variant, query, window_days) for one state, for the 12-month backfill."""
    agencies = " OR ".join(f'"{a}"' for a in AGENCIES[state])
    return [
        ("gov", f'"{state}" ({AI_QUERY}) ({GOV_QUERY})', 14),
        ("broad", f'"{state}" ({AI_QUERY})', 14),
        ("agency", f"({agencies}) ({AI_QUERY})", 30),
    ]


def load() -> dict[str, dict]:
    if not STORE.exists():
        return {}
    with open(STORE, encoding="utf-8") as f:
        return {r["guid"]: r for r in map(json.loads, f)}


def collect(start: date, end: date, window_days: int | None = None) -> int:
    """Search [start, end) and merge into the store. Returns the number of new items.

    window_days overrides each variant's window (the daily run uses one window).
    """
    items = load()
    before = len(items)
    for state in COVERED_STATES:
        for variant, query, days in queries(state):
            found = gnews.search_range(query, start, end, window_days or days)
            print(f"{state:15} {variant:6} {len(found):5} items")
            for it in found:
                row = items.setdefault(it["guid"], {**it, "variants": [], "states_queried": []})
                if variant not in row["variants"]:
                    row["variants"].append(variant)
                if state not in row["states_queried"]:
                    row["states_queried"].append(state)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    with open(STORE, "w", encoding="utf-8") as f:
        for row in items.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"collect: {len(items) - before} new, {len(items)} total in {STORE.name}")
    return len(items) - before
