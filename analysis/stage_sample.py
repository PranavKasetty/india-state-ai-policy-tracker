"""Hand-check the stage labels (pipeline/stage.py): draw a random sample, then score it.

  python -m analysis.stage_sample draw    writes analysis/stage_check.csv (40 records,
                                          an empty "human" column to fill in)
  python -m analysis.stage_sample score   compares "human" with the model's "stage"

Fill "human" with announced, decided or underway, judging from the headline and
summary as the model did (see the definitions in pipeline/stage.py).
"""
import csv
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "data" / "output" / "records.csv"
SHEET = ROOT / "analysis" / "stage_check.csv"
SIZE, SEED = 40, 20261104


def draw() -> None:
    with open(RECORDS, encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r.get("stage")]
    sample = random.Random(SEED).sample(rows, min(SIZE, len(rows)))
    with open(SHEET, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["record_id", "state", "title", "summary", "human", "stage"])
        w.writeheader()
        for r in sample:
            w.writerow({"record_id": r["record_id"], "state": r["state"], "title": r["title"],
                        "summary": r["summary"] if r["summary_source"] == "publisher standfirst" else "",
                        "human": "", "stage": r["stage"]})
    print(f"wrote {len(sample)} rows to {SHEET}; fill the 'human' column")


def score() -> None:
    with open(SHEET, encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["human"].strip()]
    if not rows:
        sys.exit("no 'human' labels yet")
    agree = sum(r["human"].strip() == r["stage"] for r in rows)
    print(f"agreement {agree}/{len(rows)} ({agree / len(rows):.0%})")
    talk = lambda s: "talk" if s == "announced" else "action"
    agree2 = sum(talk(r["human"].strip()) == talk(r["stage"]) for r in rows)
    print(f"talk vs action {agree2}/{len(rows)} ({agree2 / len(rows):.0%})")
    print("disagreements (human -> model):", Counter((r["human"].strip(), r["stage"]) for r in rows
                                                    if r["human"].strip() != r["stage"]).most_common())


if __name__ == "__main__":
    {"draw": draw, "score": score}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
