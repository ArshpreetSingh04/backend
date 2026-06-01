# LeadHunter — Progress

## Current State
- **M0 — Initialization: COMPLETE and PUSHED.**
- **M1 — Ingestion: COMPLETE — Increments 1–4 implemented.**
- **M2 — Enrichment & Scoring: IN PROGRESS — Increments 1–2 implemented.**
- The three M0 control files (PROJECT_BRIEF.md, DIRECTION.md, PROGRESS.md)
  were committed and pushed to `origin/leadhunter` at commit `c8bf3d8`.
- **Next step (Increment 3, planned):** persist enriched leads via upsert + a
  dual-sink `EnrichmentStore` (consuming the `EnrichResult`s from Increment 2).

## M0 — Initialization (COMPLETE)
- [x] Create `leadhunter/` control folder
- [x] PROJECT_BRIEF.md
- [x] DIRECTION.md
- [x] PROGRESS.md
- [x] Committed at `c8bf3d8`
- [x] Pushed to `origin/leadhunter`

## M1 — Ingestion (IN PROGRESS)

### Increment 1 — Lead model + normalize/dedup + dual persistence (DONE)
- [x] `ingestion/model.py` — `Lead` dataclass + layered dedup key + row round-trip
- [x] `ingestion/normalize.py` — `normalize_lead()` + in-memory `dedup()`
- [x] `ingestion/persistence.py` — `LeadStore` (SQLite truth + CSV mirror, idempotent)
- [x] `ingestion/README.md`
- [x] Unit tests (`tests/test_model.py`, `test_normalize.py`, `test_persistence.py`)
- [x] `python -m unittest discover -s leadhunter/tests` → 24 tests, GREEN
- [x] Stdlib-only, no network

### Increment 2 — first ingestion source (file) + pipeline (DONE)
- [x] `ingestion/sources/base.py` — `Source` ABC + `NetworkNotAllowedError`
- [x] `ingestion/sources/file_source.py` — offline `FileSource` (CSV/JSON/JSONL)
- [x] `ingestion/pipeline.py` — `ingest(sources, store, *, allow_network=False)`
      → normalize → dedup → persist; returns `IngestResult`
- [x] Responsible-use opt-in: network sources refused unless `allow_network=True`
- [x] Unit tests (`tests/test_file_source.py`, `test_pipeline.py`) incl.
      dual-sink integrity (CSV mirror == SQLite) + idempotency + network guard
- [x] `python -m unittest discover -s leadhunter/tests` → 40 tests, GREEN
- [x] Stdlib-only, no network

### Increment 3 — first network source behind opt-in (DONE)
- [x] `ingestion/sources/overpass_source.py` — `OverpassSource`
      (`requires_network = True`) over the OpenStreetMap **Overpass** open-data
      API (ODbL); maps business POIs (name/website/phone/email) to leads,
      skipping elements with no usable identity.
- [x] Responsible-use: gated by the existing `allow_network` opt-in (fail
      closed, no network at construction); honors `robots.txt`; polite delay,
      bounded timeout, descriptive `User-Agent`. Stdlib-only (`urllib`, `json`).
- [x] `ingestion/sources/__init__.py` — export `OverpassSource` +
      `RobotsDisallowedError` (additive; no core-module changes).
- [x] Unit tests (`tests/test_overpass_source.py`, 13 hermetic cases): network
      mocked via a single `_http_get` seam — no live calls. Covers mapping,
      website→domain, identity-skip, robots allow/disallow, delay, POST body,
      and pipeline opt-in refuse/allow + dual-sink integrity + idempotency.
- [x] `python -m unittest discover -s leadhunter/tests` → 53 tests, GREEN
- [x] Stdlib-only; network truly gated behind `allow_network`.

### Increment 4 — pluggable LLM provider (Ollama default + hosted fallback) (DONE)
- [x] `llm/base.py` — `LLMProvider` ABC (`generate()` + `available()`),
      error hierarchy (`LLMError`, `LLMNetworkNotAllowedError`,
      `LLMUnavailableError`), fail-closed `allow_network` opt-in.
- [x] `llm/ollama_provider.py` — `OllamaProvider` **default** (local, free):
      POST `/api/generate`, `available()` probes `/api/tags`; env overrides
      `OLLAMA_HOST` / `OLLAMA_MODEL`. Single `_http_post`/`_http_get` seam.
- [x] `llm/hosted_provider.py` — `HostedProvider` free fallback: generic
      **OpenAI-compatible** `/chat/completions`, no vendor hard-coded, env-config
      `LLM_HOSTED_BASE_URL` / `LLM_HOSTED_MODEL` / `LLM_HOSTED_API_KEY`.
- [x] `llm/factory.py` — `get_provider()` selection: `prefer`/`LLM_PROVIDER`
      override → Ollama if available → hosted fallback → clear `LLMUnavailableError`.
- [x] `llm/__init__.py` + `llm/README.md`.
- [x] Opt-in applies to **all** LLM calls including localhost Ollama (fail closed,
      no network at construction). All HTTP mocked via the seam — hermetic.
- [x] Unit tests (`tests/test_llm_base.py`, `test_ollama_provider.py`,
      `test_hosted_provider.py`, `test_llm_factory.py`): 22 new cases covering
      the opt-in guard, request bodies, response parsing, availability, env
      overrides, and selection/fallback logic. No real network/LLM calls.
- [x] `python -m unittest discover -s leadhunter/tests` → 75 tests, GREEN
- [x] Stdlib-only (`urllib`, `json`, `os`, `abc`).

## M2 — Enrichment & Scoring (IN PROGRESS)

### Increment 1 — scoring contract + RuleScorer + LLMScorer + ScoreStore (DONE)
- [x] `scoring/base.py` — `Score` (clamped 0–100, derived tier, reasons, method)
      + `Enricher` ABC + `clamp_score`/`tier_for` helpers.
- [x] `scoring/rules.py` — `RuleScorer`, the deterministic no-network floor:
      weighted identity signals (personal email +30 / role email +10, domain
      +20, company +15, name +15, phone +10, source_url +10).
- [x] `scoring/llm_scorer.py` — `LLMScorer`: optional booster behind the same
      contract, wraps a baseline + optional `LLMProvider`. Fail-closed —
      returns the baseline unchanged when network is off, no/unavailable
      provider, or unparseable reply; can only improve a valid score.
- [x] `scoring/score_store.py` — `ScoreStore` (`lead_scores` SQLite table =
      truth + derived CSV mirror, idempotent upsert/rescore) + `score_all()`
      driver. Reuses the M1 dual-sink pattern; no edits to existing code.
- [x] `scoring/__init__.py` + `scoring/README.md`.
- [x] Hermetic tests (`tests/test_scoring.py`, `test_score_store.py`, 20 new):
      RuleScorer floor/hot/role-penalty/determinism/clamp + tier boundaries;
      LLMScorer use-when-allowed + every fallback path (network off, no
      provider, unavailable, malformed JSON, LLMError) + clamp + prose
      tolerance, via an in-memory `FakeProvider`; ScoreStore dual-sink
      integrity/idempotency/reopen; `score_all` per-lead coverage + stable
      rescore. No network, no real LLM.
- [x] `python -m unittest discover -s leadhunter/tests` → 95 tests, GREEN.
- [x] Stdlib-only (`abc`, `dataclasses`, `sqlite3`, `csv`, `json`, `datetime`).

### Increment 2 — deterministic identity enrichment behind the opt-in (DONE)
- [x] `enrichment/base.py` — `IdentityEnricher` ABC (`enrich()` +
      `requires_network`), `EnrichResult` (lead/filled/method + `.changed`),
      `EnrichmentNetworkNotAllowedError`. Distinct from scoring's `Enricher`.
- [x] `enrichment/derive.py` — `DerivationEnricher` (no-network default): fills
      empty `domain` from `email` (or `source_url` when no email); only fills
      empty fields, never overwrites, always preserves `dedup_key`.
- [x] `enrichment/pipeline.py` — `enrich_all()` driver returns
      `(EnrichSummary, list[EnrichResult])`; read-only w.r.t. the store; refuses
      `requires_network` enrichers unless `allow_network=True` (fail-closed).
- [x] `enrichment/__init__.py` + `enrichment/README.md`.
- [x] Hermetic tests (`tests/test_derive.py`, `test_enrich_pipeline.py`, 16 new):
      domain-from-email/url, scheme-optional, email-preferred, no-overwrite,
      dedup_key preserved, nothing-to-fill returns same lead, determinism;
      driver summary/results, store-left-unmodified, idempotent second pass,
      network refuse/allow gate (fake network enricher), empty store.
- [x] `python -m unittest discover -s leadhunter/tests` → 111 tests, GREEN.
- [x] Stdlib-only (`abc`, `dataclasses`, `urllib.parse`). Zero edits to existing
      modules — purely additive; persistence deferred to Increment 3.

## Log
- 2026-06-01: Recreated minimal M0 control files; committed at `c8bf3d8` and
  pushed to `origin/leadhunter`. M0 COMPLETE.
- 2026-06-01: Updated PROGRESS.md to record M0 complete + pushed at `c8bf3d8`;
  next milestone is M1. (No M1 coding started this run.)
- 2026-06-01: M1 Increment 1 implemented under `leadhunter/ingestion/` — Lead
  model, normalize/dedup, dual-sink persistence (SQLite truth + CSV mirror).
  24 unit tests green via `python -m unittest discover -s leadhunter/tests`.
  Stdlib-only, no network. Recorded locked objective + Python decision in
  DIRECTION.md.
- 2026-06-01: M1 Increment 2 implemented — first ingestion source
  (`FileSource`: CSV/JSON/JSONL, offline) + `ingest()` pipeline feeding the
  existing normalize/dedup/persist flow. Responsible-use opt-in enforced via
  `NetworkNotAllowedError` (network sources refused unless `allow_network=True`).
  16 new tests incl. dual-sink integrity (CSV == SQLite) and idempotency.
  Full suite 40 tests green. Stdlib-only, no network. Next: Increment 3 — first
  network source behind the opt-in switch.
- 2026-06-01: M1 Increment 3 implemented — first **network** source
  (`OverpassSource`) over the OpenStreetMap Overpass open-data API (ODbL),
  gated by the existing `allow_network` opt-in (fail closed, no network at
  construction), honoring robots.txt with a polite delay/timeout/User-Agent.
  Maps business POIs to leads (skipping no-identity elements) through the
  unchanged normalize/dedup/persist flow. 13 hermetic tests (network mocked via
  a single `_http_get` seam — no live calls). Full suite 53 tests green.
  Stdlib-only. Next: pluggable LLM and further network sources.
- 2026-06-01: M1 Increment 4 implemented — pluggable **LLM provider** layer under
  `leadhunter/llm/`: one `generate()` interface, local **Ollama** default (free)
  and a generic **OpenAI-compatible** hosted fallback (no vendor hard-coded,
  env-configured), plus `get_provider()` selection (Ollama → hosted → clear
  error). Fail-closed `allow_network` opt-in applies to all LLM calls including
  localhost Ollama; the single HTTP seam is mocked, so 22 new tests are fully
  hermetic. Full suite 75 tests green. Stdlib-only. Next: wire the LLM into
  enrichment/scoring (M2).
- 2026-06-01: M2 Increment 1 implemented under `leadhunter/scoring/` — scoring
  contract (`Score`/`Enricher`), deterministic `RuleScorer` floor, optional
  fail-closed `LLMScorer` (improves only a valid score; falls back to the
  baseline with no network/live LLM), and dual-sink `ScoreStore` (`lead_scores`
  SQLite truth + derived CSV mirror) with a `score_all()` driver. Purely
  additive — zero edits to existing ingestion/llm code or tests. 20 new
  hermetic tests (LLM mocked via `FakeProvider`); full suite 95 tests green.
  Stdlib-only. Next: enrichment of missing identity fields (opt-in network).
- 2026-06-01: M2 Increment 2 implemented under `leadhunter/enrichment/` —
  deterministic identity enrichment behind a new `IdentityEnricher` contract
  (distinct from scoring's `Enricher`). `DerivationEnricher` (no-network
  default) fills the empty `domain` from `email`/`source_url`, only filling
  empty fields and preserving `dedup_key`. `enrich_all()` returns both
  `EnrichResult`s and an `EnrichSummary`, is read-only w.r.t. the store, and is
  fail-closed for `requires_network` enrichers. 16 new hermetic tests; full
  suite 111 tests green. Stdlib-only, purely additive. Next: Increment 3 —
  persist enriched leads via upsert + dual-sink `EnrichmentStore`.
