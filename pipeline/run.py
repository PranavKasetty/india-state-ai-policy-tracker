"""Run the pipeline: collect -> classify -> dedupe -> enrich -> export.

  python -m pipeline.run --backfill        12-month collection (first run, ~15 min)
  python -m pipeline.run --days 3          daily update: last 3 days, merged in
  python -m pipeline.run                   reprocess the stored raw items only
  add --no-enrich to skip URL resolving and summaries (fast, offline)
"""
import argparse
import hashlib
from datetime import date, timedelta

from . import collect, enrich, export
from .classify import categorise, relevance
from .dates import normalize_date
from .dedupe import cluster
from .states import state_code

BACKFILL_START = date(2025, 11, 1)

# Google News outlet names that vary for the same outlet.
SOURCE_ALIASES = {"Times of India": "The Times of India", "TOI": "The Times of India",
                  "Hindustan Times": "Hindustan Times", "HT Tech": "Hindustan Times",
                  "The Economic Times": "Economic Times", "ETGovernment.com": "Economic Times",
                  "ETTelecom.com": "Economic Times", "ETCIO.com": "Economic Times"}


def classify_all(raw: list[dict]) -> tuple[list[dict], list[dict]]:
    kept, excluded = [], []
    for it in raw:
        iso, precision = normalize_date(it["published_raw"])
        source = SOURCE_ALIASES.get(it["source_name"], it["source_name"])
        ok, reason, state, evidence = relevance(it["title"], collect.COVERED_STATES)
        base = {"guid": it["guid"], "title": it["title"], "date": iso, "date_precision": precision,
                "source_name": source, "gnews_url": it["gnews_url"], "state": state,
                "variants": it.get("variants", [])}
        if not ok:
            excluded.append({**base, "reason": reason})
            continue
        primary, tags, sector = categorise(it["title"])
        kept.append({**base, "state_code": state_code(state), "state_evidence": evidence,
                     "primary_category": primary, "tags": tags, "sector": sector})
    return kept, excluded


def build_records(kept: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Collapse duplicates. Returns (records, source_rows, audit_rows)."""
    groups, audit = cluster(kept)
    records, sources = [], []
    for g in groups:
        members = sorted((kept[i] for i in g), key=lambda r: (r["date"] or "9999", r["title"]))
        canon = members[0]
        rid = "R" + hashlib.sha1(canon["guid"].encode()).hexdigest()[:8]
        others = list(dict.fromkeys(m["source_name"] for m in members[1:]
                                    if m["source_name"] != canon["source_name"]))
        records.append({**canon, "record_id": rid, "n_sources": 1 + len(others),
                        "also_reported_by": others})
        sources += [{"record_id": rid, "source_name": m["source_name"], "title": m["title"],
                     "date": m["date"], "url": m["gnews_url"]} for m in members]
    records.sort(key=lambda r: r["date"], reverse=True)
    return records, sources, audit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, help="collect the last N days before processing")
    ap.add_argument("--backfill", action="store_true", help="collect the full 12 months")
    ap.add_argument("--no-enrich", action="store_true")
    args = ap.parse_args()

    today = date.today()
    if args.backfill:
        collect.collect(BACKFILL_START, today + timedelta(days=1))
    elif args.days:
        collect.collect(today - timedelta(days=args.days), today + timedelta(days=1), args.days + 1)

    kept, excluded = classify_all(list(collect.load().values()))
    records, sources, audit = build_records(kept)
    print(f"classify: {len(kept)} in scope, {len(excluded)} excluded -> {len(records)} records "
          f"after dedup ({len(kept) - len(records)} duplicates merged)")

    store = {} if args.no_enrich else enrich.enrich(records)
    for r in records:
        e = store.get(r["guid"], {})
        r["source_url"] = e.get("publisher_url") or r["gnews_url"]
        r["summary"] = e.get("summary") or r["title"]
        r["summary_source"] = e.get("summary_source", "headline")
        r["image_url"] = e.get("image_url", "")
    export.write_all(records, sources, excluded, audit)


if __name__ == "__main__":
    main()
