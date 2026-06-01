# LeadHunter — Direction

## Vision
Build a reliable backend that turns raw signals into qualified, actionable
sales leads.

## Locked Objective (App)
Standalone do-it-for-me lead-gen app; ONE "Find Leads" box; one natural-language
prompt; LLM agent plans, drives a browser HUMAN-LIKE, discovers/visits open-web
sources, extracts + de-duplicates + enriches leads, persists to DB AND
spreadsheet; pluggable LLM default free/local Ollama + free hosted fallback;
responsible use: prefer official APIs, respect robots.txt/rate limits/ToS, risky
scraping behind opt-in module with warnings.

## Guiding Principles
- Ship small, verifiable increments tied to milestones.
- Keep control files (this file, PROGRESS.md, PROJECT_BRIEF.md) current.
- Prefer simple, observable components over premature abstraction.

## Milestones
- **M0 — Initialization (DONE):** control files in place, repo scaffolded.
- **M1 — Ingestion (DONE):** ingest and persist raw lead sources.
- **M2 — Enrichment & Scoring (DONE):** enrich leads and assign
  qualification scores.
- **M3 — Planning & Discovery (current):** turn the one-box prompt into a
  `SearchPlan`, then discover candidate open-web sources from the plan.
- **M4 — Human-like Browsing & Extraction:** drive a real browser human-like to
  visit sources and extract raw lead records; risky scraping opt-in.
- **M5 — Dedupe + Enrich + Persist (end-to-end):** plan → discover → browse →
  extract → dedupe → enrich → score → persist to DB AND spreadsheet.
- **M6 — Acceptance & App shell:** one "Find Leads" box; acceptance:
  "Find me 50 dentists in Austin, Texas with email and phone" → 50 deduped
  enriched leads in the table AND an exportable sheet.

## M3 — Planning & Discovery
Locked objective: open the locked-objective front door — turn the single
"Find Leads" box (one natural-language prompt) into a structured, machine-readable
`SearchPlan`, then (later increment) discover candidate open-web sources from the
plan. Mirrors the M2 fail-closed pattern: a deterministic baseline always
produces a valid plan with no network/live LLM; the pluggable LLM is an
**optional** booster that can only refine (never regress) the plan.

- **Increment 1 (DONE):** prompt → `SearchPlan`. New additive
  `leadhunter/planning/` package: `SearchPlan` record + `PlanBuilder` contract;
  deterministic `RulePlanBuilder` (regex/keyword parse of count, required contact
  fields, location, and business vertical — no network); optional fail-closed
  `LLMPlanBuilder` (wraps `llm.factory` provider, merges over the baseline,
  falls back to it on network-off/no-provider/unavailable/unparseable);
  `build_plan()` driver. Stdlib-only, hermetic (LLM mocked via `FakeProvider`).
- **Later increments:** discover candidate open-web sources from a `SearchPlan`
  (prefer official APIs; responsible-use opt-in for risky scraping).

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
- **Increment 3 (DONE):** persist enriched leads via **upsert + a dual-sink
  `EnrichmentStore`** under `leadhunter/enrichment/`. Reuses the `ScoreStore`
  pattern in its own `enriched_leads` SQLite table (truth) + derived CSV mirror —
  the M1 `leads` table is never mutated. `upsert()` is fill-only and idempotent
  (only fills empty columns, unions `filled`, preserves `dedup_key`).
  `persist_enrichments()` consumes Increment 2's `EnrichResult`s;
  `enrich_and_persist()` chains enrich→persist and propagates the fail-closed
  network opt-in. Stdlib-only, hermetic (124 tests green). Purely additive.
- **Increment 4 (DONE):** opt-in **network** identity enricher
  (`WebContactEnricher`) under `leadhunter/enrichment/`. Fills empty
  `email`/`phone` by fetching the lead's **own** published website (from
  `source_url`, else `https://<domain>`) and parsing `mailto:`/`tel:` links
  (plain-text email fallback) — reading the owner's own contact page, not an
  aggregator/broker. Fail-closed behind the existing `allow_network` gate (no
  I/O at construction; none when nothing to fill or no target); honors
  `robots.txt` (`RobotsDisallowedError`), bounded `timeout`/`max_bytes`, polite
  `delay`, descriptive `User-Agent`. Only fills empty fields, preserves
  `dedup_key`. Stdlib-only, hermetic (137 tests green; network mocked via the
  `_http_get` seam). Purely additive.
- **Increment 5 (DONE):** **feed scores/enrichment back into the ingestion
  output** via a new additive `leadhunter/output/` package. `QualifiedLead` is
  the consolidated, flat record; `assemble_qualified()` **read-only** left-joins
  the three dual-sink stores by `dedup_key` — ingestion `leads` (identity truth)
  + `enriched_leads` (filled identity, preferred per-field) + `lead_scores`
  (qualification) — and sorts by score desc so the hottest leads surface first.
  `QualifiedLeadStore` persists a **fully derived snapshot** to its own
  `qualified_leads` SQLite table (truth) + derived CSV mirror; `upsert()`
  overwrites the whole row (idempotent — unchanged inputs write nothing), so a
  rebuild after a rescore/re-enrichment refreshes the output. Enrichment/scoring
  stores are optional (identity-only output when omitted); the M1 `leads` table
  and all source tables are never mutated. Stdlib-only, hermetic (152 tests
  green). Purely additive.
- **Later increments:** additional signals (e.g. richer scoring inputs, more
  opt-in network sources).

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
