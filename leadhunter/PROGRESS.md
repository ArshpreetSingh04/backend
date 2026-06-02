# LeadHunter — PROGRESS

_Work Order #1 — scaffold. Updated 2026-06-02._

## ✅ Done (this chunk)
- **Stack chosen & scaffolded:** Electron desktop shell + pure-Node core +
  `node:sqlite`. Cross-platform, zero native build, runs headlessly for CI.
- **Single "Find Leads" UI:** one prompt box + results table (`src/renderer/`),
  secure `contextBridge` IPC (`preload.js`), no Node access in the renderer.
- **Research engine behind a clean interface** (`core/researchEngine.js`):
  `ResearchEngine = { name, plan(prompt), findLeads(prompt, opts) }`. Current
  `MockResearchEngine` returns **5 mock leads** with all required fields
  (name, business, email, phone, source, hook, score).
- **Natural-language prompt parser** (`core/promptParser.js`): extracts count,
  vertical, location and desired fields. (`"find 50 dentists in Austin with
  email and phone"` → `{count:50, vertical:"dentists", location:"Austin",
  fields:["email","phone"]}`.)
- **Pipeline wired end-to-end** (`core/pipeline.js`): parse → research →
  de-dupe → **SQLite** persist → **CSV** export. Used identically by the UI and
  the CLI.
- **Persistence:** SQLite `hunts` + `leads` tables with a **unique dedupe
  index** (email → phone → name+business). CSV is a running master sheet.
- **Companion browser-extension stub** (`extension/`, MV3): installs, PING/PONG,
  naive read-only page scrape to prove content-script wiring.
- **Verification:** `test/smoke.js` passes (parse, 5 complete leads, SQLite
  write, CSV write, cross-run de-dupe). Electron shell **confirmed launching**
  under `xvfb-run` and rendering leads (screenshot captured).

## ▶️ Next step
1. **Real research engine** (`mode:'real'`): drive a real browser human-like
   (real mouse/keyboard via Playwright/CDP — never raw JS) to discover and open
   listings. `[needs-key:browser]`
2. **Source adapters**: Google Maps/Places + business directories +
   company-website extraction. `[needs-key:maps]`
3. **Enrichment + verification**: turn raw hits into verified email/phone.
   `[needs-key:enrich]`
4. **LLM-backed planner & per-lead hooks** to replace the regex parser and the
   canned hooks. `[needs-key:llm]`
5. **Live progress in the UI**: stream "what the browser is doing now" instead of
   a single status line.
6. **Per-run CSV export + download button**; let the user pick the data folder.
7. **Native-messaging bridge** between desktop app and the companion extension.
   `[needs-key:native-host]`

## 🟡 Open decisions
- **Packaging:** add `electron-builder` for installers, or stay dev-run for now?
  (Deferred — not needed for the scaffold.)
- **Engine runtime:** drive the browser in-process (Electron's own Chromium) vs.
  out-of-process via Playwright. Leaning Playwright for stealth/proxy control.
- **Data location:** `~/.leadhunter/` for now — revisit per-OS app-data dirs.
- **Dedupe strength:** currently exact-key; may want fuzzy business-name matching.
- **`node:sqlite` is experimental** — fine for the scaffold; reassess
  (better-sqlite3 / libsql) if we hit limits.
- **Scoring model:** mock scores are canned; real scoring criteria TBD.

## 🔑 [needs-key:*] — stubbed, not blocking
- `[needs-key:browser]` — real browser automation + proxy/session (Playwright/CDP).
- `[needs-key:maps]` — Google Maps / Places style business discovery.
- `[needs-key:enrich]` — email/phone enrichment & verification provider.
- `[needs-key:llm]` — LLM planner + hook generation.
- `[needs-key:native-host]` — native-messaging host for desktop ↔ extension.

_All of the above are stubbed/mocked so the scaffold runs with no keys or logins._
