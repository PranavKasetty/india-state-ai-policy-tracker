# Indian States AI Policy Tracker

A pipeline that collects news about AI and robotics activity by Indian state
governments, turns it into a deduplicated, categorised dataset, and publishes it
as a static dashboard that refreshes daily.

- **Dashboard:** https://pranavkasetty.github.io/india-state-ai-policy-tracker/
- **Dataset:** [`data/output/records.csv`](data/output/records.csv) and
  [`records.xlsx`](data/output/records.xlsx) (with a data dictionary sheet).
  See [`data/README.md`](data/README.md) for what each file and column means.
- **Coverage:** 11 states, 1 November 2025 onwards, English-language news.

## How it works

```
Google News RSS ─► collect ─► classify ─► dedupe ─► enrich ─► briefs ─► export
  (per state,       raw        rules +     TF-IDF +   publisher   LLM,      CSV, XLSX,
   3 query          items      LLM judge   LLM pair   URL,        cited     dashboard/data.js
   variants)        .jsonl                 judge      summary,
                                                      thumbnail
```

| Stage | Module | What it does |
|---|---|---|
| Scan | `pipeline/scan.py` | One-off: counts AI + government headlines for all 28 states to choose which to cover |
| Collect | `pipeline/collect.py`, `gnews.py` | Three queries per state (government terms, broad AI terms, named state agencies) in 14- or 30-day windows, merged by Google News guid |
| Normalise | `pipeline/states.py`, `dates.py` | State from names, agencies, abbreviations and cities; dates converted to IST with an explicit precision |
| Classify | `pipeline/classify.py`, `llm.py` | Keyword rules give a first in/out decision and categories; an LLM applies a written rubric to every candidate and overrides the rules when it answers |
| Dedupe | `pipeline/dedupe.py` | Same headline, then TF-IDF similarity within a state and 7 days; near misses go to an LLM "same development?" check |
| Enrich | `pipeline/enrich.py` | Resolves Google links to publisher URLs and reads the standfirst and image |
| Briefs | `pipeline/briefs.py` | 3–4 sentence summaries per state and per category, written only from the records, with every claim cited by record ID |
| Export | `pipeline/export.py` | Dataset files, audit files, and `dashboard/data.js` |

The dashboard (`dashboard/`) is plain HTML, CSS and JavaScript with no build
step. It reads `dashboard/data.js`.

## Running it

Python 3.12. From the repository root:

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; use .venv/bin/activate elsewhere
pip install -r requirements.txt

python -m pipeline.run --backfill   # first run: 12 months of news (about 15 minutes)
python -m pipeline.run --days 3     # daily update: last 3 days, merged into the store
python -m pipeline.run --no-enrich  # reprocess stored items only (fast, offline)
python -m pipeline.run --no-llm     # keyword rules only
```

Open `dashboard/index.html` in a browser to view the result.

**LLM key (optional).** Put `LLM_API_KEY=...` in a `.env` file (gitignored) or the
environment. Any OpenAI-compatible endpoint works; the default is Google Gemini's
free tier (`gemini-3.5-flash-lite`). Override with `LLM_MODEL` and `LLM_BASE_URL`.
Without a key the pipeline runs on keyword rules alone. LLM answers are cached in
`data/raw/`, so reruns are reproducible and only new items cost API calls.

## Daily refresh

- `.github/workflows/update-data.yml` runs at 08:00 IST: collects the last 3 days,
  classifies, dedupes, enriches up to 200 new records, and commits the changed
  data. The LLM key is the `LLM_API_KEY` repository secret.
- `.github/workflows/pages.yml` deploys `dashboard/` to GitHub Pages after each
  successful data run, or when the dashboard code changes.

## Repository layout

```
pipeline/            the pipeline (one module per stage)
dashboard/           static dashboard; data.js is generated
data/raw/            collected items, LLM labels and pair verdicts, enrichment (committed caches)
data/output/         the dataset and audit files
data/scan/           the 28-state scan used to choose states
analysis/            taxonomy probe and the hand-labelling sample
tests/               dashboard tests
```

## Assumptions

- **What counts.** A state government body, or the central government acting on a
  specific state, does something about AI or robotics: announces, funds, signs,
  deploys, regulates, trains, hosts, approves, or states a goal. State-backed data
  centres, state-endorsed events and state university courses count. Robotics
  counts without an AI mention. Companies, private universities and NGOs acting
  alone do not.
- **Dates** are the date of the earliest report, not of the event itself.
- **One record per development.** Reports of the same announcement by several
  outlets are merged; `n_sources` counts the outlets and is used as a rough
  popularity measure.

## Known holes

- **Headlines only.** Classification reads the headline (and outlet), not the
  article. Stories whose headline doesn't name the state or the government actor
  are missed or misjudged.
- **Google News is the only source.** Results are a relevance-ranked sample with
  no real pagination (narrow date windows recover more). Government press releases,
  gazettes and regional-language outlets are not covered.
- **LLM labels are unvalidated at scale.** The rules and the LLM agreed on 58% of
  in/out decisions before the rubric was tightened. A 60-item hand-labelled sample
  (`analysis/hand_labels/`) measures precision and recall; until it is complete,
  expect some false positives.
- **Deduplication** compares headlines within one state and 7 days. Follow-up
  stories (an MoU, then its cancellation) are kept separate on purpose; slow-moving
  stories reported more than a week apart may appear twice.
- **11 of 28 states.** Chosen from the scan (see `data/README.md`). The other 17
  are not tracked, so absence from the dashboard says nothing about their activity.
- **Link resolution and thumbnails** depend on an undocumented Google endpoint
  that rate-limits; unresolved records link to Google News and show no image.
- **The repository grows daily** because the workflow commits data.
