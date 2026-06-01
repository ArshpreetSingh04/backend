# LeadHunter — Progress

## Current State
- **M0 — Initialization: COMPLETE and PUSHED.**
- **M1 — Ingestion: IN PROGRESS — Increment 1 implemented.**
- The three M0 control files (PROJECT_BRIEF.md, DIRECTION.md, PROGRESS.md)
  were committed and pushed to `origin/leadhunter` at commit `c8bf3d8`.
- **Next step:** M1 Increment 2 — a first ingestion source feeding the
  normalize/dedup/persist pipeline (still no network until opt-in scraping).

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

### Increment 2 — first ingestion source (NEXT)
- [ ] Not started

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
