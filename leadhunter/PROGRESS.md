# LeadHunter — Progress

## Current State
- **M0 — Initialization: COMPLETE and PUSHED.**
- **M1 — Ingestion: IN PROGRESS — Increments 1, 2 & 3 implemented.**
- The three M0 control files (PROJECT_BRIEF.md, DIRECTION.md, PROGRESS.md)
  were committed and pushed to `origin/leadhunter` at commit `c8bf3d8`.
- **Next step:** later M1 increments — pluggable LLM (Ollama default + free
  hosted fallback); additional network sources as needed.

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
