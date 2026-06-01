# output — consolidated, actionable qualified leads (M2 feedback slice)

Joins the three dual-sink stores produced earlier in the pipeline into one flat,
human-readable output that *feeds scores and enrichment back into the ingestion
output*:

```
ingestion `leads`  (identity truth)
        +  enrichment `enriched_leads`  (filled identity)
        +  scoring   `lead_scores`      (qualification)
        =  output    `qualified_leads`  (best-known identity + score + provenance)
```

## What it produces

A `QualifiedLead` per ingested lead, carrying:

- **best-known identity** — the enriched value when present, otherwise the
  original ingested value (per field);
- **qualification** — `score` / `tier` / `reasons` / `score_method` (defaults
  mean "not scored yet");
- **provenance** — `enrichment_method` and the `filled` field names, so each row
  explains itself.

Rows are sorted by **score descending** (then `dedup_key`) so the most
actionable leads surface first — the same ordering convention as `ScoreStore`.

## API

```python
from leadhunter.output import (
    QualifiedLead, QualifiedSummary,
    assemble_qualified, QualifiedLeadStore, build_qualified_output,
)

# read-only join (any source store is optional)
summary, qualified = assemble_qualified(
    lead_store, enrichment_store=enriched, score_store=scores,
)

# assemble + persist to its own dual-sink store
store = QualifiedLeadStore("out/qualified.db", "out/qualified.csv")
summary, written = build_qualified_output(
    lead_store, store, enrichment_store=enriched, score_store=scores,
)
```

## Design notes

- **Read-only across sources.** The ingestion `leads`, `enriched_leads`, and
  `lead_scores` tables are never mutated; this package only *reads* them.
- **Fully derived snapshot.** Unlike the enrichment store's fill-only reconcile,
  `QualifiedLeadStore.upsert()` overwrites the whole row for a `dedup_key`, so
  re-running `build_qualified_output()` after a rescore/re-enrichment refreshes
  the output. It is idempotent: unchanged inputs write nothing.
- **Dual-sink.** SQLite is the source of truth; the CSV is regenerated from
  SQLite after every write, so the two can never diverge — matching `LeadStore`,
  `ScoreStore`, and `EnrichmentStore`.
- **Stdlib-only, no network.**
