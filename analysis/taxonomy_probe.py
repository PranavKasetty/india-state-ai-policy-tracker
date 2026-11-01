"""Probe the draft taxonomy against real headlines (exploration, not part of the pipeline).

Takes every headline from the scan cache that names a state and mentions AI, applies
draft keyword tags, and reports:
  - how often each tag fires and how many headlines get no tag (missing categories?)
  - which tags co-occur (where multi-labelling matters, or categories overlap)
  - a sample of untagged headlines to read
It also writes a random sample for hand-coding, with no suggested labels (to avoid
anchoring the coder), to analysis/coding_sample.csv.

Usage:  python -m analysis.taxonomy_probe
"""
import csv
import random
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

from pipeline import gnews
from pipeline.scan import END, START, UNION_TERRITORIES, WINDOW_DAYS
from pipeline.states import STATES, find_states
from pipeline.terms import AI_QUERY, AI_RE, GOV_QUERY

DRAFT_TAGS = {
    "strategy_policy": r"\bpolic(y|ies)\b|\bmission\b|strategy|roadmap|vision|blueprint|action plan",
    "governance_body": r"task force|committee|council|advisory|\bboard\b|agenc(y|ies)|directorate|\bcell\b|panel|authority",
    "regulation_ethics": r"regulat|guideline|framework|ethic|\brules?\b|mandatory|\bban\b|approval|privacy|standard",
    "infrastructure": r"data cent(re|er)|compute|GPU|supercomput|AI (city|park|hub|valley)|centre of excellence|\bCoE\b|incubat|\blab\b",
    "partnership": r"\bMoU\b|\bpact\b|partner|tie[- ]?up|join hands|collaborat|agreement|\binks?\b",
    "deployment": r"\blaunch|deploy|roll(s|ed)? out|introduc|AI[- ](based|powered|enabled|driven)|\bpilot\b|\buses? AI\b|using AI",
    "funding_budget": r"budget|crore|allocat|\bfund|grant|invest|₹|\bRs\.?\b|\$|billion|lakh",
    "skilling": r"train|skill|course|curriculum|literacy|fellowship|academy",
    "events_outreach": r"summit|conclave|conference|hackathon|expo|workshop",
}
TAG_RES = {k: re.compile(v, re.IGNORECASE) for k, v in DRAFT_TAGS.items()}
OUT = Path(__file__).resolve().parent / "coding_sample.csv"
SAMPLE_SIZE = 80


def headlines_by_state() -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for state in STATES:
        if state in UNION_TERRITORIES:
            continue
        items = gnews.search_range(f'"{state}" ({AI_QUERY}) ({GOV_QUERY})', START, END, WINDOW_DAYS)
        out[state] = [it for it in items
                      if state in find_states(it["title"])[0] and AI_RE.search(it["title"])]
    return out


def main() -> None:
    by_state = headlines_by_state()
    titles = list({it["title"] for items in by_state.values() for it in items})
    tags = {t: [k for k, rx in TAG_RES.items() if rx.search(t)] for t in titles}

    print(f"{len(titles)} unique headlines\n\nTag frequency:")
    freq = Counter(k for ks in tags.values() for k in ks)
    for k in DRAFT_TAGS:
        print(f"  {k:18} {freq[k]:5}  ({freq[k] / len(titles):.0%})")
    n_tags = Counter(len(ks) for ks in tags.values())
    print("\nTags per headline:", dict(sorted(n_tags.items())))

    print("\nMost common co-occurring pairs:")
    pairs = Counter(p for ks in tags.values() for p in combinations(sorted(ks), 2))
    for (a, b), n in pairs.most_common(10):
        print(f"  {a} + {b}: {n}")

    random.seed(7)
    untagged = [t for t, ks in tags.items() if not ks]
    print(f"\nSample of untagged headlines ({len(untagged)} total):")
    for t in random.sample(untagged, min(30, len(untagged))):
        print("  -", t[:120])

    # Simple random sample over all headlines, so states appear in proportion to volume.
    pool = [(s, it) for s, items in by_state.items() for it in items]
    rows = [{"state": s, "title": it["title"], "source": it["source_name"], "in_scope": "",
             "primary_category": "", "tags": "", "sector": "", "notes": ""}
            for s, it in sorted(random.sample(pool, SAMPLE_SIZE), key=lambda p: p[0])]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {len(rows)} rows for hand-coding to {OUT}")


if __name__ == "__main__":
    main()
