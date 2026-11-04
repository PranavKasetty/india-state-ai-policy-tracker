# Regional-language probe, October 2026

`python -m analysis.regional_probe` searched Google News in each state's main language
for October 2026 (state name + AI terms, weekly windows). The LLM applied the tracker's
rubric to each translated headline, said whether the actor was state-level or local,
and looked for the same development among the English headlines the pipeline collected
for that state (19 Sep - 4 Nov). One row per headline is in `items.csv`.

## Counts

Regional headlines judged in scope whose original headline has an AI or robotics term
(108 "in scope" headlines with no AI term were dropped as noise):

| State | Language | Oct records in dataset (English) | In scope, state-level | Not in our English collection | In it, but excluded by the rubric |
|---|---|---|---|---|---|
| Uttar Pradesh | Hindi | 29 | 54 | 24 | 5 |
| Madhya Pradesh | Hindi | 11 | 32 | 20 | 8 |
| Bihar | Hindi | 10 | 33 | 6 | 7 |
| Rajasthan | Hindi | 1 | 11 | 10 | 0 |
| Maharashtra | Marathi | 19 | 17 | 12 | 2 |
| Gujarat | Gujarati | 12 | 7 | 3 | 1 |
| West Bengal | Bengali | 2 | 5 | 3 | 2 |
| Telangana | Telugu | 6 | 10 | 4 | 2 |
| Andhra Pradesh | Telugu | 13 | 8 | 5 | 1 |
| Tamil Nadu | Tamil | 7 | 11 | 3 | 4 |
| Kerala | Malayalam | 15 | 1 | 0 | 0 |
| Punjab | Punjabi | 9 | 2 | 0 | 1 |
| **Total** | | **134** | **191** | **90** | **33** |

Karnataka (Kannada) and Odisha (Odia): Google News has no edition for either language
and returned nothing, so they cannot be covered this way.

## What the numbers mean

- The 90 are headlines, not developments: several outlets report the same story, and a
  few are filed under the wrong state (an MP story in the UP list). Reading the UP, MP,
  Rajasthan and Maharashtra lists suggests roughly 60% are distinct, so about 55
  developments, against 134 October records for these states: **about +40%**.
- The gain is concentrated in the Hindi states and Maharashtra. Rajasthan goes from 1
  October record to about 6, MP roughly doubles, and UP gains about half. Kerala, Punjab,
  Tamil Nadu and the Telugu states gain little: English coverage there is already good.
- What English misses is mostly **implementation**: department- and district-level
  deployments (AI towers against illegal sand mining in Chambal, AI checks on jail
  kitchens and medicine samples, an AI "water budget" for 23,011 MP panchayats, AI in
  exam invigilation), training programmes, and some state-level items (UP AI Mission,
  the UPAM AI centre of excellence, an Indore AI and IT campus, AI in the Rajasthan Board
  syllabus). Flagship announcements usually do appear in English.
- Precision is lower than for English: Google's regional search matches loosely, and
  without the AI-term filter nearly a third of "in scope" items (108 of 347) had no AI term.

## Limits

One month; headlines only; the in-scope and matching judgements are the LLM's and were
not hand-checked; "not in our English collection" means our queries did not find an
English report, not that none exists.
