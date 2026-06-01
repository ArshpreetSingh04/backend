# LeadHunter — Progress

## Current State
- **M0 — Initialization: COMPLETE and PUSHED.**
- **M1 — Ingestion: IN PROGRESS — Increments 1 & 2 implemented.**
- The three M0 control files (PROJECT_BRIEF.md, DIRECTION.md, PROGRESS.md)
  were committed and pushed to `origin/leadhunter` at commit `c8bf3d8`.
- **Next step:** M1 Increment 3 — the first **network** ingestion source
  (scraper) behind the opt-in `allow_network` switch + human-like browsing.

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

### Increment 3 — first network source behind opt-in (NEXT)
- [ ] Not started — scraper source (`requires_network = True`) gated by
      `allow_network`, with human-like browsing per the locked principles.

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
