"""Stage 3 - collapse duplicate reports of the same announcement.

Three layers, cheapest first:
  1. same Google News guid           (done in collect: one row per guid)
  2. same normalised headline        (wire copy: PTI/IANS stories reprinted verbatim)
  3. similar headline, same state, published within WINDOW_DAYS of each other
     (TF-IDF cosine >= THRESHOLD; different outlets rewording one announcement)
Clusters are merged with union-find. The earliest report becomes the canonical
record; the rest are kept as "also reported by". Every layer-3 merge is written to
the audit file with its similarity, so the threshold can be checked by eye.
"""
import math
import re
from collections import Counter
from datetime import date

THRESHOLD = 0.5
WINDOW_DAYS = 7
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


def cluster(records: list[dict]) -> tuple[list[list[int]], list[dict]]:
    """Group record indexes into duplicate clusters. Returns (clusters, audit_rows)."""
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

    vecs = _tfidf([tokens(r["title"]) for r in records])  # layer 3
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            ri, rj = records[i], records[j]
            if ri["state"] != rj["state"] or find(i) == find(j):
                continue
            if _days(ri["date"], rj["date"]) > WINDOW_DAYS:
                continue
            sim = _cosine(vecs[i], vecs[j])
            if sim >= THRESHOLD:
                parent[find(j)] = find(i)
                audit.append({"layer": "similar headline", "similarity": round(sim, 3),
                              "kept_title": ri["title"], "merged_title": rj["title"]})

    groups: dict[int, list[int]] = {}
    for i in range(len(records)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values()), audit
