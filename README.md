# Indian States AI Policy Tracker

A pipeline that collects news about AI and robotics activity by Indian state
governments, turns it into a deduplicated, categorised dataset, and publishes it
as a static dashboard that refreshes daily.

- **Dashboard:** https://pranavkasetty.github.io/india-state-ai-policy-tracker/
- **Dataset:** [`data/output/records.csv`](data/output/records.csv) and
  [`records.xlsx`](data/output/records.xlsx) (with a data dictionary sheet).
  See [`data/README.md`](data/README.md) for what each file and column means.
- **Coverage:** all 28 states, 1 November 2025 onwards, English-language news.

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
| Scan | `pipeline/scan.py` | One-off: counts AI + government headlines for all 28 states (used to choose the first 11; all 28 are now covered) |
| Collect | `pipeline/collect.py`, `gnews.py` | Three queries per state (government terms, broad AI terms, named state agencies) in 14- or 30-day windows, merged by Google News guid |
| Normalise | `pipeline/states.py`, `dates.py` | State from names, agencies, abbreviations and cities; dates converted to IST with an explicit precision |
| Classify | `pipeline/classify.py`, `llm.py` | Keyword rules give a first in/out decision and categories; an LLM applies a written rubric to every candidate and overrides the rules when it answers |
| Dedupe | `pipeline/dedupe.py` | Same headline, then TF-IDF similarity within a state and 7 days; near misses go to an LLM "same development?" check |
| Enrich | `pipeline/enrich.py` | Resolves Google links to publisher URLs and reads the standfirst and image |
| Stage | `pipeline/stage.py` | How far each development has gone: announced, decided (approved, signed) or underway (launched, in use). A separate LLM pass, so inclusion is unchanged |
| Briefs | `pipeline/briefs.py` | 3–4 sentence summaries per state and per category, written only from the records, with every claim cited by record ID |
| State status | `pipeline/profiles.py` | One row per state: AI policy, dedicated AI body, state AI funding, AI infrastructure, each with a status and the record IDs behind it |
| Export | `pipeline/export.py`, `pages.py` | Dataset files, audit files, `dashboard/data.js`, a static page and RSS feed per state, the site feed and the sitemap |

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

- `.github/workflows/update-data.yml` is scheduled for 05:47 IST (00:17 UTC);
  GitHub often starts scheduled runs hours late. It collects the last 3 days,
  classifies, dedupes, enriches up to 200 new records, and commits the changed
  data. It also runs on pushes to `main` that change `pipeline/`,
  `requirements.txt` or the workflow, and can be started by hand with a larger
  enrichment limit. The LLM key is the `LLM_API_KEY` repository secret.
- `.github/workflows/pages.yml` deploys `dashboard/` to GitHub Pages after each
  successful data run, or when the dashboard code changes.

## Repository layout

```
pipeline/            the pipeline (one module per stage)
dashboard/           static dashboard; data.js is generated
data/raw/            collected items, LLM labels and pair verdicts, enrichment (committed caches)
data/output/         the dataset and audit files
data/scan/           the 28-state scan used to choose the first states
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
- **The LLM misses some real items.** On a random sample of 60 hand-labelled
  headlines (`analysis/hand_labels/scores.csv`), the rubric in use (v2) had 97%
  precision and 81% recall: about one in five real developments is left out,
  such as company-run programmes in a state and court rulings. The earlier v1
  rubric had higher recall (91%) but let in more items where the government was
  not the actor. A sample of 60 gives wide error margins.
- **Deduplication** compares headlines within one state and 7 days. Follow-up
  stories (an MoU, then its cancellation) are kept separate on purpose; slow-moving
  stories reported more than a week apart may appear twice.
- **Coverage, not activity.** Counts measure how much English-language news
  covered a state's AI work. Large states and tech hubs get more coverage; small
  north-eastern states have only a handful of records, which says little about
  their activity.
- **Link resolution and thumbnails** depend on an undocumented Google endpoint
  that rate-limits; unresolved records link to Google News and show no image.
- **The repository grows daily** because the workflow commits data.
