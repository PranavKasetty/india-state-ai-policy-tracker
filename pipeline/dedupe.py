"""Stage 3 - collapse duplicate reports of the same announcement.

Layers, cheapest first. Layers 3-5 only compare reports from the same state
published within WINDOW_DAYS of each other.
  1. same Google News guid           (done in collect: one row per guid)
  2. same normalised headline        (wire copy: PTI/IANS stories reprinted verbatim)
  3. similar headline                (TF-IDF cosine >= THRESHOLD)
  4. near miss, FLOOR <= cosine < THRESHOLD, decided by
       - an LLM judge ("same development?") when an API key is set, else
       - a shared figure with a unit ("12 lakh", "Rs 10,000 crore") as a fallback rule.
Rewordings of one announcement often score 0.25-0.5 ("12 Lakh Youth To Get AI
Training" vs "Train 12 Lakh Youth In AI"). The figure rule alone over-merges
follow-ups that repeat the amount (an MoU and its cancellation), hence the judge.
Clusters are merged with union-find. The earliest report becomes the canonical
record; the rest are kept as "also reported by". Every merge is written to the
audit file with its layer and similarity, so it can be checked by eye.
"""
import math
import re
from collections import Counter
from datetime import date
from typing import Callable

THRESHOLD = 0.5
FLOOR = 0.25
WINDOW_DAYS = 7
# An amount with a unit: "12 lakh", "₹10,000 crore", "$4 billion", "500 MW", "40%".
FIGURE_RE = re.compile(r"(\d[\d,.]*)\s*(lakh|crore|cr\b|billion|bn\b|million|mn\b|MW|GW|%|per ?cent)", re.I)
STOPWORDS = set("""a an the of to in on for and or with by at from as is are be will its it this
that into over under after new govt government state says said says""".split())


def tokens(title: str) -> list[str]:
    words = re.findall(r"[a-z0-9₹]+", title.lower())
    return [w.rstrip("s") if len(w) > 4 else w for w in words if w not in STOPWORDS]


def _tfidf(docs: list[list[str]]) -> list[dict[str, float]]:
    df = Counter(t for d in docs for t in set(d))
    n = len(docs)
    vecs = []
    for d in docs:
        tf = Counter(d)
        v = {t: c * math.log((1 + n) / (1 + df[t])) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def _days(a: str, b: str) -> int:
    if len(a) < 10 or len(b) < 10:  # missing or reduced-precision dates: don't use the window
        return 0
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def figures(title: str) -> set[str]:
    return {f"{n.replace(',', '').rstrip('.')} {u.lower()}" for n, u in FIGURE_RE.findall(title)}


Judge = Callable[[list[tuple[dict, dict]]], list[bool | None]]


def cluster(records: list[dict], judge: Judge | None = None) -> tuple[list[list[int]], list[dict]]:
    """Group record indexes into duplicate clusters. Returns (clusters, audit_rows).
    judge(pairs) -> one True/False/None per pair; None or no judge = not merged."""
    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    audit = []
    by_title: dict[str, int] = {}
    for i, r in enumerate(records):  # layer 2
        key = " ".join(re.findall(r"[a-z0-9]+", r["title"].lower()))
        if key in by_title:
            parent[find(i)] = find(by_title[key])
            audit.append({"layer": "exact headline", "similarity": 1.0,
                          "kept_title": records[by_title[key]]["title"], "merged_title": r["title"]})
        else:
            by_title[key] = i

    def merge(i: int, j: int, layer: str, sim: float) -> None:
        parent[find(j)] = find(i)
        audit.append({"layer": layer, "similarity": round(sim, 3),
                      "kept_title": records[i]["title"], "merged_title": records[j]["title"]})

    vecs = _tfidf([tokens(r["title"]) for r in records])
    near = []  # (i, j, sim) in the FLOOR..THRESHOLD band
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            ri, rj = records[i], records[j]
            if ri["state"] != rj["state"] or _days(ri["date"], rj["date"]) > WINDOW_DAYS:
                continue
            sim = _cosine(vecs[i], vecs[j])
            if sim >= THRESHOLD and find(i) != find(j):  # layer 3
                merge(i, j, "similar headline", sim)
            elif FLOOR <= sim < THRESHOLD:
                near.append((i, j, sim))

    near = [(i, j, sim) for i, j, sim in near if find(i) != find(j)]  # layer 4
    if judge:
        verdicts = judge([(records[i], records[j]) for i, j, _ in near])
        for (i, j, sim), same in zip(near, verdicts):
            if same and find(i) != find(j):
                merge(i, j, "llm: same development", sim)
    else:
        for i, j, sim in near:
            if find(i) != find(j) and figures(records[i]["title"]) & figures(records[j]["title"]):
                merge(i, j, "shared figure", sim)

    groups: dict[int, list[int]] = {}
    for i in range(len(records)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values()), audit
