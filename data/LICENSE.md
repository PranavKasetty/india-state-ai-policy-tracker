# Data license

The dataset in this folder (`data/output/`, `data/raw/`, `data/scan/`) and the data
the dashboard shows (`dashboard/data.js`, the state pages and feeds) are licensed under
the **Creative Commons Attribution 4.0 International license (CC BY 4.0)**:
https://creativecommons.org/licenses/by/4.0/

You may copy, share and adapt the data, including for commercial use, as long as you
give credit and say if you changed it. Suggested credit:

> Indian States AI Policy Tracker, Pranav Kasetty, 2026.
> https://pranavkasetty.github.io/india-state-ai-policy-tracker/ (CC BY 4.0)

## What the license covers

The license covers what this project made:

- the selection and arrangement of the records, and the record IDs;
- the labels: inclusion decisions, types of activity, sectors, stages, states, dates
  and duplicate merges;
- the English translations of Hindi and Marathi headlines;
- the AI-generated briefs (`briefs.json`) and the state status table
  (`state_status.csv`, `profiles.json`);
- the scan counts and audit files.

## What it does not cover

News headlines, the publishers' first sentences (`summary` when `summary_source` is
`publisher standfirst`), original-language headlines (`title_original`) and linked
images belong to their publishers. They are included as short quotations so that each
record can be identified and checked against its source, which it links to. They are
not licensed here; reproducing them beyond that use is a matter between you and the
publisher.

The data is provided as is, without warranty. It is built from news reports by
automated methods and contains errors; see `data/README.md` for its known limits.
