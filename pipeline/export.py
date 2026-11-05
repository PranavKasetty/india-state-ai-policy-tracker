"""Stage 5 - write the dataset (CSV + XLSX), audit files, and the dashboard's JSON."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook

from .classify import CATEGORIES, CATEGORY_IDS, SECTORS
from . import pages
from .profiles import FIELDS as PROFILE_FIELDS, apply_curated
from .stage import LABELS as STAGE_LABELS
from .states import state_code

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "output"
DASHBOARD_JS = ROOT / "dashboard" / "data.js"

# Column order and meaning of the main dataset. Also written as the XLSX data dictionary.
COLUMNS = {
    "record_id": "Stable ID derived from the earliest report of the announcement",
    "state": "Canonical state name (normalised from names, abbreviations, agencies, cities)",
    "state_code": "ISO 3166-2:IN code",
    "date": "Date first reported, in IST. ISO 8601 at the precision known (YYYY-MM-DD / YYYY-MM / YYYY)",
    "date_precision": "day | month | year | unknown",
    "title": "Headline of the earliest report (an English translation when that report is in Hindi or Marathi)",
    "language": "Language of the earliest report: en, hi (Hindi) or mr (Marathi)",
    "title_original": "The headline as published, when it is not in English",
    "summary": "One line: the publisher's standfirst, or the headline when unavailable",
    "summary_source": "publisher standfirst | headline",
    "primary_category": "Single main category (priority order in classify.CATEGORIES)",
    "tags": "All matching categories, separated by '; '",
    "sector": "Policy domain the activity applies to",
    "stage": "How far it has gone: announced (plan, proposal, statement) | decided (approved, signed, "
             "allocated) | underway (launched, in use, held). LLM-judged from the headline and standfirst",
    "source_name": "Outlet of the earliest report",
    "source_url": "Publisher URL (Google News link when it could not be resolved)",
    "n_sources": "Number of distinct outlets that reported it",
    "also_reported_by": "Other outlets, separated by '; ' (full list in sources.csv)",
    "state_evidence": "How the state was identified: name | agency | abbrev | city",
    "classified_by": "llm (rubric applied by an LLM, cached) | rules (keyword rules, no LLM label)",
}


# Shown in the XLSX "about" sheet, for anyone who only has the spreadsheet.
ABOUT = {
    "title": "Indian States AI Policy Tracker",
    "source": "https://pranavkasetty.github.io/india-state-ai-policy-tracker/",
    "license": "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) - see data/LICENSE.md",
    "not covered": "Headlines and publishers' summaries are quoted for reference and remain the publishers'",
    "credit": "Indian States AI Policy Tracker, Pranav Kasetty, 2026 (CC BY 4.0)",
    "method": "https://github.com/PranavKasetty/india-state-ai-policy-tracker/blob/main/data/README.md",
}


def _flat(r: dict) -> dict:
    return {k: "; ".join(r[k]) if isinstance(r.get(k), list) else r.get(k, "") for k in COLUMNS}


def _csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel reads ₹ correctly
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_all(records: list[dict], sources: list[dict], excluded: list[dict], audit: list[dict],
              briefs: dict[str, dict], profiles: dict[str, dict] | None = None) -> None:
    profiles = {s: {f: p[f] for f in PROFILE_FIELDS if f in p} for s, p in apply_curated(profiles or {}).items()}
    OUT.mkdir(parents=True, exist_ok=True)
    flat = [_flat(r) for r in records]
    _csv(OUT / "records.csv", flat, list(COLUMNS))
    _csv(OUT / "sources.csv", sources, ["record_id", "source_name", "title", "date", "url", "language", "title_original"])
    _csv(OUT / "excluded.csv", excluded, ["reason", "state", "date", "title", "source_name", "gnews_url"])
    _csv(OUT / "dedupe_audit.csv", audit, ["layer", "similarity", "kept_title", "merged_title"])
    status_rows = [{"state": s, **{f"{f}{suffix}": (p.get(f) or {}).get(key, "") if key != "cites"
                                   else "; ".join((p.get(f) or {}).get("cites", []))
                                   for f in PROFILE_FIELDS for suffix, key in
                                   (("_status", "status"), ("", "text"), ("_records", "cites"))},
                    **{f"{f}_link": (p.get(f) or {}).get("document") or (p.get(f) or {}).get("source", "")
                       for f in PROFILE_FIELDS}}
                   for s, p in sorted(profiles.items())]
    _csv(OUT / "state_status.csv", status_rows,
         ["state", *[f"{f}{x}" for f in PROFILE_FIELDS for x in ("_status", "", "_records", "_link")]])

    wb = Workbook()
    sheets = [("records", flat, list(COLUMNS)),
              ("sources", sources, ["record_id", "source_name", "title", "date", "url", "language", "title_original"]),
              ("data_dictionary", [{"column": k, "meaning": v} for k, v in COLUMNS.items()],
               ["column", "meaning"]),
              ("about", [{"item": k, "value": v} for k, v in ABOUT.items()], ["item", "value"])]
    for i, (name, rows, fields) in enumerate(sheets):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = name
        ws.append(fields)
        for row in rows:
            ws.append([row.get(f, "") for f in fields])
        ws.freeze_panes = "A2"
    wb.save(OUT / "records.xlsx")

    write_dashboard(records, briefs, profiles)
    print(f"export: {len(records)} records, {len(excluded)} excluded, {len(audit)} merges -> {OUT}")


def write_dashboard(records: list[dict], briefs: dict[str, dict], profiles: dict[str, dict]) -> None:
    """Write dashboard/data.js in the shape documented in dashboard/mock_data.py."""
    if not records:  # never replace a working dashboard with an empty one
        print("export: no records, dashboard/data.js left unchanged")
        return
    cats = [(CATEGORY_IDS[c], c) for c in [*CATEGORIES, "Other"]]
    dates = sorted(r["date"] for r in records if r["date"])
    items = [{"id": r["record_id"], "date": r["date"], "date_precision": r["date_precision"],
              "state": r["state"], "title": r["title"], "summary": r["summary"],
              "source": r["source_name"], "url": r["source_url"], "image": r["image_url"],
              "category": CATEGORY_IDS[r["primary_category"]],
              "tags": [CATEGORY_IDS[t] for t in r["tags"]], "sector": r["sector"], "stage": r.get("stage", ""),
              "n_sources": r["n_sources"], "also_reported_by": r["also_reported_by"],
              **({"lang": r["language"], "title_original": r["title_original"]} if r.get("language", "en") != "en" else {})}
             for r in records]
    meta = {"is_mock": False,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "period_start": dates[0] if dates else "", "period_end": dates[-1] if dates else "",
            "states": [{"name": s, "code": state_code(s)} for s in sorted({r["state"] for r in records})],
            "categories": [{"id": i, "label": label} for i, label in cats],
            "sectors": [*SECTORS, "Cross-cutting"],
            "stages": [{"id": k, "label": v} for k, v in STAGE_LABELS.items()],
            # AI-generated, citation-checked summaries: {"states": {name: brief}, "categories": {id: brief}}
            "briefs": {"states": {k[6:]: v for k, v in briefs.items() if k.startswith("state:")},
                       "categories": {k[9:]: v for k, v in briefs.items() if k.startswith("category:")},
                       **({"overall": briefs["overall"]} if "overall" in briefs else {})},
            # AI-drafted, cited status per state: {state: {field: {status, text, cites}}}
            "profiles": profiles}
    js = ("// Generated by pipeline/export.py from data/output/records.csv. Do not edit.\n"
          f"window.TRACKER_DATA = {json.dumps({'meta': meta, 'items': items}, ensure_ascii=False, indent=1)};\n")
    DASHBOARD_JS.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_JS.write_text(js, encoding="utf-8")
    pages.write_all(records, briefs, profiles)
