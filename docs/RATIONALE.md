# Rationale

**Goal.** Track what Indian state governments do about AI: one row per
development, refreshed daily, viewable by state and by type.

## Sources

I used **Google News RSS search** (India edition, English). It is free and needs
no key. It aggregates hundreds of Indian outlets, including regional English
papers that national news APIs index poorly, and it supports date operators
(`after:` / `before:`). I compared it with the free tiers of news APIs
(NewsAPI, GNews, NewsData). Those cap requests at around 100 a day and history
at 30 days or less, which can't cover a 12-month backfill for many states.
Government press releases and gazettes would be more authoritative, but each
state publishes them differently, so that would mean a scraper per state. I left
them as the main extension. I looked at the OECD.AI India dashboards and
IndiaAI's articles for framing. Neither lists state-level activity.

## Which states, and why

I ran the same query for all 28 states over 12 months and counted headlines that
name the state, an AI term and a government signal (`data/scan/state_scan.csv`).
The top ten (Karnataka 130 down to Punjab 53) sit above a clear drop to Assam (39),
so I took them as the first tier. I added Andhra Pradesh (32) on substance: the
Google data centre in Visakhapatnam and its real-time governance work are among
the year's larger state AI stories. Counts moved between runs (Maharashtra 98,
then 69), so I read the scan as tiers, not as a ranking. Covering 11 states well
seemed better than 28 thinly: each extra state adds queries, false positives to
check, and agency lists to research.

## How the data is collected and cleaned

- **Recall.** Google returns about 100 results per query and has no pagination.
  So each state gets three queries (government terms, broad AI terms, its named
  agencies such as T-Hub or TNeGA), each run over 14- or 30-day windows. Splitting
  one quarter into months raised results from 31 to 106.
- **Relevance.** The test is that a state body, or the centre acting on one state,
  acts on AI or robotics. Keyword rules handle the clear exclusions: no AI term,
  social posts, Pakistani outlets, and items outside the window. An LLM (Gemini
  free tier) applies a written rubric to the rest. The rules and the LLM agreed on
  only 58% of headlines. Where they disagreed, the LLM was usually right but too
  generous with private-company news, so I tightened the rubric. A random 60-item
  hand-labelled sample measures both.
- **Normalisation.** States are detected from names, agencies, abbreviations and
  cities, recording which one matched. Dates are converted to IST and stored at
  their known precision. Each record's date is the earliest report.
- **Deduplication.** Exact headlines, then TF-IDF similarity within a state and
  7 days. Rewordings scoring 0.25–0.5 go to an LLM "same development?" check, and
  every merge is logged in an audit file.
- **Reproducibility.** LLM answers are cached by prompt version and committed, so
  a rerun gives the same dataset without a key.

## Presentation

The dashboard is a static page on GitHub Pages. A GitHub Actions job refreshes the
data every morning, so there is no server to maintain. It opens on the list of
developments with filters for state, type and sector. Rankings by state and by
type, and a monthly chart, give the overview. Each card shows the outlet count
and links to the publisher. Short AI briefs per state and per type cite the
records they draw on, so every claim can be checked.

## Known limits

Classification uses headlines only. There is no regional-language news. The counts
measure coverage, not activity. The other 17 states are untracked.
