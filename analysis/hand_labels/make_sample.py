"""Draw the hand-labelling sample: a simple random sample of LLM candidates
(headline names a covered state and an AI/robotics term, not hard-excluded).
Sampling from candidates, not from kept records, lets the labels measure both
precision and recall of the rules and of each LLM prompt version."""
import csv
import hashlib
import json
import random
from pathlib import Path

from pipeline import collect
from pipeline.run import classify_all

N, SEED = 60, 2026
OUT = Path(__file__).parent / "sample.csv"

kept, excluded = classify_all(list(collect.load().values()), use_llm=False)
hard_out = ("no AI", "social media", "before the tracking window", "foreign outlet", "no covered state")
pool = [r for r in kept] + [r for r in excluded if r["state"] and not any(h in r["reason"] for h in hard_out)]
pool.sort(key=lambda r: r["guid"])
sample = random.Random(SEED).sample(pool, N)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["item_id", "guid", "state", "date", "source_name", "title", "url"])
    for r in sample:
        w.writerow(["H" + hashlib.sha1(r["guid"].encode()).hexdigest()[:8], r["guid"], r["state"],
                    r["date"], r["source_name"], r["title"], r["gnews_url"]])
print(f"{len(pool)} candidates, {N} sampled -> {OUT}")
