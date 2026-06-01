# enrichment

The *enrichment* half of M2: fill **missing** identity fields on a `Lead` behind
a single contract, with a deterministic no-network default and a fail-closed
network opt-in.

## Contract

```python
class IdentityEnricher(abc.ABC):
    name: str = "enricher"
    requires_network: bool = False
    def enrich(self, lead: Lead) -> EnrichResult: ...
```

- `EnrichResult(lead, filled, method)` — `lead` is the possibly-updated lead
  (a new `Lead` when fields were filled, else the original unchanged), `filled`
  names the fields newly populated, `method` records the producer. `.changed`
  is `True` when anything was filled.
- Enrichers only ever **fill empty** fields — never overwrite — and always
  **preserve `dedup_key`** so persistence identity stays stable.

> Naming: scoring's `scoring/base.py` defines a separate `Enricher` that returns
> a `Score`. `IdentityEnricher` is a *different* contract (it fills fields) and
> lives in its own package to avoid collision.

## Enrichers

- **`DerivationEnricher`** (`requires_network = False`) — the default path. Pure,
  deterministic, no I/O. Derives the structured `domain` field from fields
  already present: from `email` (part after `@`), or from `source_url` (host)
  when no email is available. Fields that can't be derived deterministically
  (e.g. email, phone) are out of scope and belong to a later opt-in network
  enricher.

## Driver

```python
summary, results = enrich_all(lead_store, enricher, *, allow_network=False)
```

Reads leads from a `LeadStore`, enriches each, and returns BOTH the per-lead
`EnrichResult`s (in store order) and an `EnrichSummary(processed, changed,
filled_by_field)`. **Read-only** with respect to the store — this slice does not
write enriched leads back.

A `requires_network` enricher is refused with `EnrichmentNetworkNotAllowedError`
unless `allow_network=True` (fail-closed), mirroring the ingestion pipeline.

## Persistence (`EnrichmentStore`)

```python
store = EnrichmentStore(db_path, csv_path)
persist_enrichments(results, store)                 # consume enrich_all() output
# or, in one call:
processed, persisted = enrich_and_persist(lead_store, enricher, store,
                                          *, allow_network=False)
```

Dual-sink persistence for enriched leads, reusing the `ScoreStore`/`LeadStore`
pattern in its **own** `enriched_leads` table + derived CSV mirror — the M1
`leads` table is never mutated. **SQLite is the source of truth**; the CSV is
regenerated *from* SQLite after every write, so the two never diverge.

- Keyed by `dedup_key` (the stable, layered identity key the whole pipeline uses).
- `upsert(result)` is **fill-only**: a repeat `dedup_key` only populates columns
  that are currently empty (never overwriting a non-empty value), unions the
  recorded `filled` field names, and refreshes `method`/`enriched_at`. Returns
  whether the row changed, so `persist_enrichments` is idempotent.
- Each row stores the enriched `Lead` snapshot (`Lead.COLUMNS`) plus enrichment
  metadata (`filled`, `method`, `enriched_at`); `all()` returns `(Lead, meta)`
  pairs read back from SQLite.

## Next increment

Opt-in **network** identity enricher (fill `email`/`phone` that can't be derived
deterministically), then feed scores/enrichment back into ingestion outputs.

## Tests

`python -m unittest discover -s leadhunter/tests` — stdlib-only, hermetic, no
network.
