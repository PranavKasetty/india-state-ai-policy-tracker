"""Coverage scan: how much AI-and-government news exists for each of the 28 states?

This is a prioritisation tool, not the dataset. For every state it searches Google
News month by month over the last 12 months and counts headlines that
  (a) name the state (via states.find_states),
  (b) mention AI (terms.AI_RE), and
  (c) carry a rough government signal (terms.GOV_RE).
(c) is a crude keyword proxy, used only to rank states, not to decide what goes in
the dataset. Monthly windows keep the method identical across states; the main
collection uses weekly windows for higher recall.

Usage:  python -m pipeline.scan            -> data/scan/state_scan.csv
"""
import csv
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from . import gnews
from .states import STATES, find_states
from .terms import AI_QUERY, AI_RE, GOV_QUERY, GOV_RE

START, END = date(2025, 11, 1), date(2026, 11, 1)  # last 12 months
WINDOW_DAYS = 30
OUT = Path(__file__).resolve().parent.parent / "data" / "scan" / "state_scan.csv"
UNION_TERRITORIES = {"Delhi", "Jammu and Kashmir", "Puducherry"}  # out of scope for the scan


@dataclass
class ScanRow:
    state: str
    raw_results: int = 0
    state_and_ai_in_headline: int = 0
    plus_gov_signal: int = 0


def scan_state(state: str) -> ScanRow:
    items = gnews.search_range(f'"{state}" ({AI_QUERY}) ({GOV_QUERY})', START, END, WINDOW_DAYS)
    row = ScanRow(state, raw_results=len(items))
    for it in items:
        if state in find_states(it["title"])[0] and AI_RE.search(it["title"]):
            row.state_and_ai_in_headline += 1
            row.plus_gov_signal += bool(GOV_RE.search(it["title"]))
    return row


def main() -> None:
    rows = [scan_state(s) for s in STATES if s not in UNION_TERRITORIES]
    rows.sort(key=lambda r: -r.plus_gov_signal)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(rows[0])))
        w.writeheader()
        w.writerows(asdict(r) for r in rows)
    for r in rows:
        print(f"{r.state:18} state+AI={r.state_and_ai_in_headline:4}  +gov={r.plus_gov_signal:4}"
              f"  raw={r.raw_results:4}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
