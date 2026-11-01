# About the data

Each row of `output/records.csv` is one **development**: an action on AI or
robotics by an Indian state government, or by the central government in a way
tied to one state, as reported in English-language news from 1 November 2025.
Several reports of the same development are merged into one row.

## Files

| File | What it holds |
|---|---|
| `output/records.csv` / `records.xlsx` | The dataset, one row per development. The XLSX adds a `sources` sheet and a `data_dictionary` sheet |
| `output/sources.csv` | Every report behind each record (`record_id`, outlet, headline, date, link) |
| `output/excluded.csv` | Every collected headline that was left out, with the reason |
| `output/dedupe_audit.csv` | Every merge: which layer merged it, the similarity score, and both headlines |
| `output/briefs.json` | The AI-written summaries per state and per category, with the record IDs each one cites |
| `raw/items.jsonl` | Everything collected from Google News, one line per item |
| `raw/llm_labels.jsonl` | The LLM's label for each candidate headline, by prompt version (cache) |
| `raw/llm_pairs.jsonl` | The LLM's same-development verdict for each near-duplicate pair (cache) |
| `raw/enriched.jsonl` | Publisher URL, standfirst and image per record (cache) |
| `scan/state_scan.csv` | The 28-state scan used to choose which states to cover |

CSV files are UTF-8 with a byte-order mark, so Excel shows ₹ correctly.

## Columns (`records.csv`)

| Column | Meaning |
|---|---|
| `record_id` | Stable ID, `R` + 8 hex characters, derived from the earliest report |
| `state`, `state_code` | Canonical state name and ISO 3166-2:IN code |
| `date` | Date of the earliest report, in IST, at the precision known: `YYYY-MM-DD`, `YYYY-MM` or `YYYY` |
| `date_precision` | `day`, `month`, `year` or `unknown` |
| `title` | Headline of the earliest report |
| `summary` | The publisher's standfirst (first sentence), or the headline when it could not be fetched |
| `summary_source` | `publisher standfirst` or `headline` |
| `primary_category` | The single main category (below) |
| `tags` | All categories that apply, separated by `; ` |
| `sector` | Policy area: Health, Agriculture, Education, Policing & safety, Urban & transport, Revenue & citizen services, Industry & startups, or Cross-cutting |
| `source_name` | Outlet of the earliest report |
| `source_url` | Publisher URL; a Google News link when it could not be resolved |
| `n_sources` | Number of distinct outlets that reported it |
| `also_reported_by` | The other outlets, separated by `; ` |
| `state_evidence` | How the state was identified: `name`, `agency` (e.g. T-Hub, TNeGA), `abbrev` (e.g. "UP govt") or `city` |
| `classified_by` | `llm` (rubric applied by the LLM) or `rules` (keyword rules; no LLM label available) |

## Categories

Multi-label. The primary category is the LLM's choice, or for rule-labelled rows
the first match in this order.

| ID | Label | Covers |
|---|---|---|
| `strategy_policy` | Strategy & policy | Policies, missions, roadmaps, stated goals by a CM or minister |
| `regulation_ethics` | Regulation & ethics | Rules, guidelines, frameworks, mandates, data governance |
| `governance_body` | Governance bodies | Task forces, committees, AI cells, new departments |
| `funding_budget` | Funding & budget | Budget allocations, funds, grants, investment commitments |
| `infrastructure` | Infrastructure | Data centres, compute, centres of excellence, AI cities and labs |
| `partnership` | Partnership / MoU | MoUs and tie-ups with companies, universities or foundations |
| `deployment` | Deployment | AI used in a government service or operation |
| `skilling` | Skilling | Training officials, teachers or students; courses and curricula |
| `events_outreach` | Events & outreach | Summits, hackathons, challenges hosted or endorsed by the state |
| `other` | Other | In scope, but none of the above |

The categories were drafted from the news itself (`analysis/taxonomy_probe.py`
counts tag frequency and overlap) rather than taken from the OECD.AI policy
instrument types, which describe national strategies and fit state-level news
poorly.

## How states were chosen

`scan/state_scan.csv` ran the same Google News query for all 28 states over the
12 months and counted the headlines that name the state, an AI term, and a
government signal (`plus_gov_signal`).

- The top ten (Karnataka 130 down to Punjab 53) are covered. The next state,
  Assam, drops to 39.
- **Andhra Pradesh** (32) is added despite the lower count, for substance: the
  Google data centre in Visakhapatnam and the state's real-time governance work
  are among the larger state AI developments of the year.
- Counts vary between runs (Maharashtra came out at 98 in one run and 69 in
  another), so the scan is read as tiers, not an exact ranking.
- Goa returned zero, which probably reflects a query problem rather than no
  activity. It was not investigated.

## How rows are made

1. **Collect.** For each state, three Google News RSS queries: the state + AI
   terms + government terms; the state + AI terms; and the state's named AI and IT
   agencies + AI terms. Each runs over narrow date windows (14 or 30 days)
   because Google returns at most about 100 items per query.
2. **Normalise.** The state is found in the headline from its name, an agency, a
   common abbreviation, or a major city, in that order of confidence. Publication
   times are converted from UTC to IST before taking the date.
3. **Exclude outright:** headlines with no AI or robotics term, social media posts,
   Pakistani outlets (whose "Punjab" is Pakistan's), and items dated before
   1 November 2025.
4. **Judge.** Every remaining headline that names a covered state goes to the LLM
   with the inclusion rubric (`pipeline/llm.py`). Its answer overrides the keyword
   rules; the rules stand in when it has not answered.
5. **Merge duplicates** within a state and 7 days: identical headlines, then
   TF-IDF similarity ≥ 0.5, then pairs between 0.25 and 0.5 that the LLM judges to
   be the same development. The earliest report is kept.
6. **Enrich** the publisher link, standfirst and image, newest records first, up
   to 200 a day.

## Assumptions and known holes

- **Report date, not event date.** A cabinet decision reported a day later is
  dated by the report.
- **Headline-only judgement.** Neither the rules nor the LLM read the article.
- **Coverage, not activity.** Counts measure how much the news covered a state's
  AI activity. States with more English-language business press look more active.
- **Not validated yet.** A random sample of 60 candidate headlines is being hand
  labelled (`analysis/hand_labels/`) to measure precision and recall of the rules
  and the LLM.
- **Missing sources.** No government press releases, gazettes, assembly records
  or regional-language news.
- **AI briefs** are generated from these records only and cite record IDs.
  Uncited claims are removed, but the wording still needs a human check before it
  is quoted.
