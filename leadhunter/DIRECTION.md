# LeadHunter — Direction

## Vision
Build a reliable backend that turns raw signals into qualified, actionable
sales leads.

## Guiding Principles
- Ship small, verifiable increments tied to milestones.
- Keep control files (this file, PROGRESS.md, PROJECT_BRIEF.md) current.
- Prefer simple, observable components over premature abstraction.

## Milestones
- **M0 — Initialization (DONE):** control files in place, repo scaffolded.
- **M1 — Ingestion (DONE):** ingest and persist raw lead sources.
- **M2 — Enrichment & Scoring (current):** enrich leads and assign
  qualification scores.

## M2 — Enrichment & Scoring
Locked objective: turn persisted leads into qualification **scores** behind a
single `Enricher` contract. A deterministic baseline always produces a score
without any network/live LLM; the pluggable LLM is an **optional** booster that
can only ever improve a valid score (fail-closed). Scores persist to BOTH
SQLite (truth) and a derived CSV mirror, reusing the M1 dual-sink pattern.

- **Increment 1 (DONE):** scoring contract (`Score`, `Enricher`) + deterministic
  `RuleScorer` floor (identity completeness/quality, role-email penalty) +
  optional `LLMScorer` (wraps `llm.factory` provider, fail-closed fallback to
  baseline) + dual-sink `ScoreStore` (`lead_scores` table + derived CSV mirror)
  and `score_all()` driver. Stdlib-only, hermetic (95 tests green; LLM mocked
  via a `FakeProvider`). Code under `leadhunter/scoring/`.
- **Increment 2 (DONE):** deterministic **identity enrichment** behind a new
  `IdentityEnricher` contract (distinct from scoring's `Enricher`) under
  `leadhunter/enrichment/`. `DerivationEnricher` is the no-network default —
  fills the empty `domain` field from `email` (or `source_url`), only ever
  *filling* empty fields and always preserving `dedup_key`. `enrich_all()`
  driver returns both per-lead `EnrichResult`s (in-memory artifact + handoff to
  the persistence increment) and an `EnrichSummary`; it is read-only w.r.t. the
  store and refuses `requires_network` enrichers unless `allow_network=True`
  (fail-closed). Stdlib-only, hermetic (111 tests green). Purely additive.
- **Increment 3 (NEXT, planned):** persist enriched leads via **upsert + a
  dual-sink `EnrichmentStore`** (consuming the `EnrichResult`s from Increment 2).
- **Later increments:** opt-in **network** identity enricher (fill email/phone
  that can't be derived deterministically); feed scores back into ingestion
  outputs; additional signals.

## M1 — Ingestion
Locked objective: ingest raw lead sources and **persist to BOTH a database and
a spreadsheet**, with a pluggable LLM, human-like browsing, and responsible
scraping behind an opt-in switch.

- **Increment 1 (DONE):** core `Lead` model + normalize/dedup +
  dual-sink persistence (SQLite = source of truth, CSV = derived mirror).
  Stdlib-only, unit-tested, no network. Code under `leadhunter/ingestion/`.
- **Increment 2 (DONE):** first ingestion source — offline `FileSource`
  (CSV/JSON/JSONL) + `ingest()` pipeline feeding normalize/dedup/persist.
  Responsible-use opt-in enforced now via `NetworkNotAllowedError` (network
  sources refused unless `allow_network=True`). Stdlib-only, unit-tested.
- **Increment 3 (DONE):** first **network** source — `OverpassSource` over the
  OpenStreetMap Overpass open-data API (ODbL) behind the `allow_network` opt-in,
  honoring robots.txt + polite rate limiting. Stdlib-only, network mocked in
  tests (53 total, green).
- **Increment 4 (DONE):** pluggable **LLM provider** layer — one `generate()`
  interface over one "box". Local **Ollama** default (free) + generic
  **OpenAI-compatible** hosted fallback (no vendor hard-coded, env-configured) +
  `get_provider()` selection. Fail-closed `allow_network` opt-in applies to all
  LLM calls (including localhost Ollama); single HTTP seam mocked in tests
  (75 total, green). Code under `leadhunter/llm/`.
- **Later increments:** wire the LLM into enrichment/scoring (M2); additional
  network sources as needed.

## Decisions
- Control files live under `leadhunter/` and are versioned with the code.
- **Language: Python 3, stdlib-only** for M1 Increment 1 (`unittest`,
  `sqlite3`, `csv`, `json`, `hashlib`) — zero third-party deps, runs offline.
- **Dual persistence:** SQLite is the source of truth; the spreadsheet (CSV)
  is a derived mirror regenerated from SQLite so the two never diverge.
- **Pluggable LLM (locked, DONE in M1 Inc.4):** local **Ollama** is the default
  with a generic OpenAI-compatible free hosted fallback (env-configured). All
  LLM calls are fail-closed behind the `allow_network` opt-in.
- **Scraping (locked, later):** human-like browsing; responsible scraping is
  **opt-in** only.
- **Dedup key:** deterministic, layered — email > domain+company >
  company+name > sha1 fallback; used as the SQLite primary key for idempotency.
