# LeadHunter

> The first automation in a larger **business backend** platform.

A *do-it-for-me* lead finder. The entire UI is one **Find Leads** box: type a
natural-language prompt (e.g. *"find 50 dentists in Austin with email and
phone"*) and LeadHunter plans the search, researches open-web sources, then
qualifies / de-duplicates / enriches the leads and writes them to a **SQLite
database** *and* a **CSV** spreadsheet.

This repo is the **Work Order #1 scaffold** — small and functional, not perfect.
The research is currently a **mock** that returns 5 leads; everything around it
(UI → pipeline → DB → CSV → de-dupe) is real and wired together.

## Stack
- **Electron** — cross-platform desktop shell (Win/Mac/Linux). Its Node main
  process is where the future *real browser* automation (human-like
  mouse/keyboard via Playwright/CDP, **never** raw JS injection) will live.
- **`node:sqlite`** — local database, built into Node 22 (no native build step).
- **Pure Node core modules** — engine, storage, CSV, pipeline. No runtime deps,
  so the whole thing runs and is testable headlessly.

## Layout
```
leadhunter/
├─ src/
│  ├─ main.js              Electron main process (window + IPC)
│  ├─ preload.js           secure contextBridge -> window.leadhunter
│  ├─ renderer/            the UI: index.html, styles.css, renderer.js
│  ├─ core/
│  │  ├─ researchEngine.js clean ResearchEngine interface (MOCK impl)
│  │  ├─ promptParser.js   NL prompt -> {count, vertical, location, fields}
│  │  ├─ storage.js        SQLite (hunts + leads, unique dedupe index)
│  │  ├─ csv.js            dependency-free CSV writer
│  │  └─ pipeline.js       parse -> research -> dedupe -> persist -> csv
│  └─ cli.js               headless runner (same pipeline, no GUI)
├─ extension/              MV3 companion browser-extension stub
└─ test/smoke.js           end-to-end pipeline smoke test
```

## Run it
```bash
cd leadhunter
npm install

# Desktop app
npm start
# Headless server/CI (Linux without a display):
npm run start:headless        # uses xvfb-run

# Headless pipeline (no GUI) — great for scripting & verification
npm run hunt -- "find 50 dentists in Austin with email and phone"   # mock
npm run hunt -- --real "find 50 dentists in Austin"                 # real browser, live web

# Tests / verification
npm run smoke         # mock pipeline: parse -> research -> dedupe -> SQLite -> CSV
npm run verify:real   # REAL Chromium drives a local fixture search engine end-to-end
```

### Real browser engine (Playwright)
`mode:'real'` uses **Playwright + Chromium**, driven human-like (real
navigation, mouse, keyboard, scrolling — never injected JS). Install the browser
once:
```bash
npx playwright install chromium
# (or set PLAYWRIGHT_BROWSERS_PATH to a pre-provisioned browsers dir)
```
The current real source adapter is a **general web search** (open engine → type
`niche + location` → open top organic results → extract business name +
website/domain + source URL). Contact `email`/`phone`/`hook` are left empty and
flagged `[needs-key:enrich]` — never faked. A Maps/Places adapter is stubbed
(`[needs-key:maps]`).

> **Egress note:** if your environment has a network allowlist that blocks the
> open web, the *live* path can't reach search engines (`[needs-key:network-egress]`).
> `npm run verify:real` proves the engine end-to-end against a local fixture
> regardless. See **PROGRESS.md**.

> In a container you may need `--no-sandbox` (Chromium setuid sandbox):
> `npm run start:headless -- --no-sandbox`.

## Where your data goes
By default everything lands in `~/.leadhunter/`:
- `leadhunter.db` — SQLite (`hunts` + `leads`, deduped via a unique index)
- `leads.csv` — running master spreadsheet of every stored lead

The desktop app's **Open data folder** button reveals it.

## Mock ↔ real
`createEngine({ mode })` in `src/core/researchEngine.js` is the seam.
- `mode:'mock'` → `MockResearchEngine` (5 canned leads; default).
- `mode:'real'` → `RealResearchEngine` (`src/core/realResearchEngine.js`) which
  drives a real browser via the web-search adapter.

Both implement the same `plan()` / `findLeads()` contract, so the UI, pipeline,
DB and CSV are unchanged either way.

See **PROGRESS.md** for status and the `[needs-key:*]` list.
