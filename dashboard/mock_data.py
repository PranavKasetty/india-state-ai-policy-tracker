"""Write placeholder data for the dashboard while the real dataset is being built.

Same shape as pipeline/export.py's output (contract: dashboard/schema.py), and the
same taxonomy, taken from pipeline/classify.py and pipeline/export.py, so the
dashboard can be designed against realistic structure before the real run.

Everything here is synthetic: headlines and summaries are built from templates and
marked "[Mock]", outlets are "Example outlet N", links are empty, and thumbnails
are generated SVGs. To exercise edge cases, some items have no image, a broken
image link, a month- or year-only date, or no date. State volumes are weighted by
the scan's plus_gov_signal counts so relative sizes look plausible.

Usage:  python -m dashboard.mock_data            -> dashboard/data.js
        python -m dashboard.mock_data --force    replace a real export too

data.js is also where pipeline/export.py writes the real dataset, so this refuses
to overwrite a real export unless --force is given.
"""
import argparse
import csv
import sys
import random
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dashboard import schema
from pipeline.agencies import AGENCIES
from pipeline.classify import CATEGORIES, SECTORS
from pipeline.export import CATEGORY_IDS
from pipeline.states import state_code

SCAN = Path(__file__).resolve().parent.parent / "data" / "scan" / "state_scan.csv"
START, END = date(2025, 11, 1), date(2026, 10, 31)
N_ITEMS = 640
SEED = 11

CATEGORY_LIST = [(CATEGORY_IDS[c], c) for c in [*CATEGORIES, "Other"]]
SECTOR_LIST = [*SECTORS, "Cross-cutting"]
SECTOR_PHRASE = {s: s.lower() for s in SECTORS} | {"Cross-cutting": "government services"}

BASE_WEIGHT = {"strategy_policy": 6, "regulation_ethics": 3, "governance_body": 4,
               "funding_budget": 7, "infrastructure": 8, "partnership": 12,
               "deployment": 22, "skilling": 10, "events_outreach": 9, "other": 3}
TEMPLATES = {
    "strategy_policy": ["{state} cabinet clears draft AI policy",
                        "{body} publishes AI roadmap for {sector}",
                        "{state} announces state AI mission"],
    "regulation_ethics": ["{state} issues guidelines on AI use in departments",
                          "{state} drafts framework for responsible AI in {sector}",
                          "{state} mandates labels on AI-generated official content"],
    "governance_body": ["{state} sets up AI task force under chief secretary",
                        "{state} names new head of {body}",
                        "{state} forms expert committee on AI in {sector}"],
    "funding_budget": ["{state} budget allocates funds for AI mission",
                       "{state} announces AI startup fund via {body}",
                       "{state} sanctions grant for AI in {sector}"],
    "infrastructure": ["{state} plans AI compute facility with {body}",
                       "{body} opens centre of excellence for AI",
                       "{state} approves land for AI data centre park"],
    "partnership": ["{body} signs MoU with tech firm on AI for {sector}",
                    "{state} partners university on AI research",
                    "{state} inks pact for AI pilots in {sector}"],
    "deployment": ["{state} rolls out AI chatbot for {sector}",
                   "{state} pilots AI tool in {sector}",
                   "{body} deploys AI cameras for monitoring",
                   "{state} launches AI-based grievance tracking"],
    "skilling": ["{state} to train government staff in AI",
                 "{body} launches AI skilling programme for students",
                 "{state} adds AI course to school curriculum"],
    "events_outreach": ["{state} hosts AI conclave with {body}",
                        "{body} holds AI hackathon on {sector}",
                        "{state} officials showcase AI projects at summit"],
    "other": ["{state} minister comments on AI and jobs",
              "{state} assembly debates AI in {sector}"],
}
CO_TAGS = {
    "strategy_policy": ["funding_budget", "governance_body"],
    "regulation_ethics": ["strategy_policy", "deployment"],
    "governance_body": ["strategy_policy", "regulation_ethics"],
    "funding_budget": ["infrastructure", "strategy_policy"],
    "infrastructure": ["funding_budget", "partnership"],
    "partnership": ["deployment", "skilling", "infrastructure"],
    "deployment": ["partnership"],
    "skilling": ["partnership", "events_outreach"],
    "events_outreach": ["partnership", "skilling"],
    "other": [],
}
# Month-level bumps so the time series has some shape.
MONTH_BOOST = {(2026, 2): {"events_outreach": 3.0, "partnership": 1.6},
               (2026, 3): {"funding_budget": 3.0}}
THUMB_COLOURS = ["#c9c1ee", "#b9d4c8", "#e6d3b3", "#c4d2e6", "#e3c4cf"]


def state_weights() -> dict[str, int]:
    with open(SCAN, encoding="utf-8") as f:
        counts = {r["state"]: int(r["plus_gov_signal"]) for r in csv.DictReader(f)}
    return {s: max(counts.get(s, 1), 1) for s in AGENCIES}


def mock_thumbnail(rng: random.Random) -> str:
    """A small striped SVG as a data URI, standing in for a publisher's og:image."""
    bg, fg = rng.sample(THUMB_COLOURS, 2)
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 160'><defs><pattern id='p' "
           f"width='{rng.choice([18, 26, 34])}' height='10' patternUnits='userSpaceOnUse' "
           f"patternTransform='rotate({rng.choice([35, 145])})'><rect width='8' height='10' "
           f"fill='{fg}'/></pattern></defs><rect width='240' height='160' fill='{bg}'/>"
           f"<rect width='240' height='160' fill='url(#p)'/></svg>")
    return "data:image/svg+xml," + urllib.parse.quote(svg, safe=" '=/:")


def mock_date(rng: random.Random) -> tuple[str, str]:
    span = (END - START).days
    d = START + timedelta(days=int(rng.triangular(0, span, span * 0.85)))  # more recent items
    roll = rng.random()
    if roll < 0.90:
        return d.isoformat(), "day"
    if roll < 0.96:
        return d.isoformat()[:7], "month"
    if roll < 0.99:
        return d.isoformat()[:4], "year"
    return "", "unknown"


def holds_real_export(path: Path) -> bool:
    if not path.exists():
        return False
    with open(path, encoding="utf-8") as f:
        return "dashboard/mock_data.py" not in f.readline()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="overwrite data.js even if it holds a real export")
    if holds_real_export(schema.DATA_PATH) and not ap.parse_args().force:
        sys.exit(f"{schema.DATA_PATH} holds a real export from the pipeline; "
                 "rerun with --force to replace it with mock data.")
    rng = random.Random(SEED)
    weights = state_weights()
    states = list(weights)
    cat_ids = [c for c, _ in CATEGORY_LIST]
    lean = {s: {c: BASE_WEIGHT[c] * rng.uniform(0.4, 1.8) for c in cat_ids} for s in states}
    outlets = [f"Example outlet {n}" for n in range(1, 10)]

    items = []
    for i in range(N_ITEMS):
        state = rng.choices(states, [weights[s] for s in states])[0]
        iso, precision = mock_date(rng)
        boost = MONTH_BOOST.get((int(iso[:4]), int(iso[5:7])), {}) if len(iso) >= 7 else {}
        category = rng.choices(cat_ids, [lean[state][c] * boost.get(c, 1) for c in cat_ids])[0]
        sector = rng.choices(SECTOR_LIST, [3, 2, 3, 2, 2, 3, 3, 5])[0]
        title = rng.choice(TEMPLATES[category]).format(
            state=state, body=rng.choice(AGENCIES[state]), sector=SECTOR_PHRASE[sector])
        title = "[Mock] " + title[0].upper() + title[1:]
        has_summary = rng.random() < 0.7  # otherwise the pipeline falls back to the headline
        source = rng.choice(outlets)
        others = rng.sample([o for o in outlets if o != source], min(8, int(rng.expovariate(0.8))))
        roll = rng.random()
        image = "" if roll < 0.2 else "https://example.invalid/broken.jpg" if roll < 0.23 else mock_thumbnail(rng)
        items.append({
            "id": f"M{i:04d}",
            "date": iso,
            "date_precision": precision,
            "state": state,
            "title": title,
            "summary": (f"[Mock] Placeholder standfirst describing what the {state} item is about, "
                        f"cut to one sentence as the pipeline does.") if has_summary else title,
            "source": source,
            "url": "",
            "image": image,
            "category": category,
            "tags": [category, *[t for t in CO_TAGS[category] if rng.random() < 0.25]],
            "sector": sector,
            "n_sources": 1 + len(others),
            "also_reported_by": others,
        })
    items.sort(key=lambda it: it["date"], reverse=True)

    data = {
        "meta": {
            "is_mock": True,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "period_start": START.isoformat(),
            "period_end": END.isoformat(),
            "states": [{"name": s, "code": state_code(s)} for s in sorted(states)],
            "categories": [{"id": c, "label": label} for c, label in CATEGORY_LIST],
            "sectors": SECTOR_LIST,
        },
        "items": items,
    }
    out = schema.write(data, generator="dashboard/mock_data.py from synthetic templates")
    print(f"wrote {len(items)} mock items to {out}")


if __name__ == "__main__":
    main()
