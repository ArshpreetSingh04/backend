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
- **M1 — Ingestion (current):** ingest and persist raw lead sources.
- **M2 — Enrichment & Scoring:** enrich leads and assign qualification scores.

## M1 — Ingestion
Locked objective: ingest raw lead sources and **persist to BOTH a database and
a spreadsheet**, with a pluggable LLM, human-like browsing, and responsible
scraping behind an opt-in switch.

- **Increment 1 (current):** core `Lead` model + normalize/dedup +
  dual-sink persistence (SQLite = source of truth, CSV = derived mirror).
  Stdlib-only, unit-tested, no network. Code under `leadhunter/ingestion/`.
- **Later increments:** scrapers + human-like browsing; pluggable LLM
  (Ollama default + free hosted fallback); opt-in responsible-scraping switch.

## Decisions
- Control files live under `leadhunter/` and are versioned with the code.
- **Language: Python 3, stdlib-only** for M1 Increment 1 (`unittest`,
  `sqlite3`, `csv`, `json`, `hashlib`) — zero third-party deps, runs offline.
- **Dual persistence:** SQLite is the source of truth; the spreadsheet (CSV)
  is a derived mirror regenerated from SQLite so the two never diverge.
- **Pluggable LLM (locked, later):** local **Ollama** is the default with a
  free hosted fallback.
- **Scraping (locked, later):** human-like browsing; responsible scraping is
  **opt-in** only.
- **Dedup key:** deterministic, layered — email > domain+company >
  company+name > sha1 fallback; used as the SQLite primary key for idempotency.
