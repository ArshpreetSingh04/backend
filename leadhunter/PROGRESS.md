# LeadHunter — PROGRESS

_Updated 2026-06-02. Work Order #7 — anti-bot hardening + block diagnostics._

## ✅ Done — Work Order #7 (real discovery: anti-detection + clear block diagnostics)
Grounded in a real live run (Arsh provisioned Chromium and ran `--real` against
the open web): the human-like browser now launches & navigates, but DuckDuckGo
served an anti-bot page (redirect to `static-pages/418.html`) and discovery died
on a silent 20s selector timeout. This increment makes humaning less detectable
and turns silent failures into precise diagnostics. **No raw HTTP/fetch** — all
discovery stays real-browser human-like.
- **UA aligned with the REAL browser** (`humanBrowser.js`): the User-Agent is now
  derived from `browser.version()` (was a hardcoded `Chrome/124` while the binary
  is Chromium 141 — a detection tell). Verified: outgoing UA = `Chrome/141`.
- **Automation signal stripped** at launch via `--disable-blink-features=AutomationControlled`
  (a launch flag — no JS injection), plus realistic context: `Accept-Language`,
  `locale`, `timezoneId`.
- **Block/challenge detection** (`webSearchAdapter.js`): after navigation (and on
  any selector timeout) the adapter checks for challenge URLs
  (`static-pages/4xx`, `/sorry`, `/captcha`, …) and "unusual traffic"-style text,
  then **fails fast** with a specific message AND a **`blocked` progress event** —
  instead of a silent 20s timeout. Plain timeouts now also report the current URL.
- **Alternate provider + headed mode** (opt-in, still real-browser):
  `LEADHUNTER_PROVIDER=bing` (new Bing provider config) and `LEADHUNTER_HEADFUL=1`
  (full headed Chromium under xvfb) as levers to get past screening.
- **Verified OFFLINE** (egress is blocked in this sandbox, so live DDG is
  unreachable here): new `npm run verify:antibot` proves (1) the UA matches the
  real Chromium major + Accept-Language is sent, and (2) a blocking fixture
  (302 → `/static-pages/418.html`) triggers the diagnostic + `blocked` event in
  **~0.8s** (not a 20s hang). `verify:real`, `smoke`, `test:engine`, `test:parser`
  all still pass. (Live `--real` here fails cleanly at navigation with a clear
  message, confirming graceful failure.)

## ✅ Done — Work Order #6 (mock/real toggle + live progress)
- **Mock/real toggle** in the desktop UI ("Use real research engine") next to the
  Find Leads box. **Default stays MOCK** for safety; toggling on runs the pipeline
  with `mode:'real'` (the real `RealResearchEngine` path).
- **Structured progress events** streamed engine → pipeline → IPC → UI: a tiny
  `progress(phase, message, data)` helper (`src/core/progress.js`) threads through
  both engines and the web-search + enrichment adapters. Phases: `parsing-prompt`,
  `searching`, `business-found`, `qualifying`, `enriching`, `persisted`, `done`,
  `error`. Rendered as a **live activity list** under the box (with phase icons),
  so the user sees what the humaning engine is doing instead of a frozen screen.
- **Wired through the existing clean interface** (`opts.onProgress` on the
  pipeline, `progress` on the engine) — **no new raw JS / synthetic events** added
  to the product browser automation.
- **Real leads flow into the same table + SQLite + CSV** as mock (unchanged
  persistence path).
- **Verified OFFLINE:** `npm run verify:real` now also asserts the event stream
  (21 events, 8 `business-found`, all phases present) alongside the existing
  leads→DB→CSV + enrichment checks. A headless Electron boot confirms the toggle
  renders and a mock hunt streams progress through the real IPC path into the
  table. `smoke`, `test:engine`, `test:parser` still pass.

## ✅ Done — Work Order #5 (enrichment adapter)
- **New `enrichmentAdapter`** (`src/core/adapters/enrichmentAdapter.js`): for each
  lead missing a required, enrichable field (**email/phone**), it visits the
  lead's own site (its `source` page), follows a **Contact/About** link, and reads
  the email/phone off the page — all **human-like** (real `goto` navigation +
  real mouse click via the existing `HumanBrowser` seam). **No raw JS / synthetic
  events**; DOM reads (`mailto:`/`tel:` links, then visible-text fallback) are used
  only for extraction.
- **Never fabricates:** a field is filled only if actually found; missing values
  stay `null`.
- **Plugs in behind the clean interface:** runs inside `findLeads()` after
  qualification, before the pipeline's dedupe/persistence. After enrichment the
  lead is **re-scored** via the now-shared `scoreLead()`, so filling a required
  field **removes its down-rank penalty** automatically.
- **3rd-party verification stubbed:** `verifyEmail()` is a no-op placeholder
  (deliverability/MX check needs an API key) — we don't claim validity yet.
  `[needs-key:enrich]`
- **Offline-testable:** the fixture now serves **/contact/:id** pages (mailto/tel)
  and a Contact link on each biz page; one business (b2) has email-only to exercise
  honest partial enrichment.
- **Verified:** `npm run verify:real` shows rank-1 enriched (email+phone) with its
  penalty removed (**score 76 → 100**) and rank-2 partially enriched (email only,
  phone left `null`, **score 80**). New offline `scoreLead` test proves penalty
  removal (76→100; partial 80). `test:engine`, `test:parser`, `smoke` all pass.

## ✅ Done — Work Order #4 (engine consumes TargetProfile)
- **`RealResearchEngine.plan()` now consumes the rich TargetProfile** (via
  `parseTargetProfile`) instead of the legacy `parsePrompt` view: `niche/role`,
  `location`, `count`, `requiredContactFields`, `extraQualifiers`.
- **Query shaping:** `plan()` builds a `query` from **niche + location +
  extraQualifiers** (e.g. `"plumbers Denver 5 star reviews"`); the web-search
  adapter now types this shaped query (falls back to niche+location for older
  callers).
- **Qualification + scoring uses the profile** (pure, exported `qualifyLeads()`):
  a lead needs a business name + website to exist; a missing **verifiable-now**
  required field (`website`) **drops** the lead; a missing enrichment-gated field
  (`email`/`phone`/…) **down-ranks** it (−12 each), never faked
  `[needs-key:enrich]`; each matched **extraQualifier** boosts the score (+6).
- **`parsePrompt()` kept as a backward-compatible shim** for the mock engine, CLI
  and smoke test. Default mock-vs-real entry points were **not** touched.
- **Verified OFFLINE:** new `npm run test:engine` (query shaping + scoring,
  no browser); `npm run verify:real` now asserts `plan()` reflects
  `requiredContactFields` + `extraQualifiers` for **dentists & plumbers** and that
  scoring folds them in end-to-end (rank-1 = **76**, not 100, for missing
  email+phone). `npm run test:parser` and `npm run smoke` still pass.

## ✅ Done — Work Order #3 (prompt → TargetProfile parser)
- **Real deterministic parser** (`src/core/promptParser.js`) converts any
  Find-Leads prompt into a structured **TargetProfile**:
  `{ raw, niche, role, location, count, requiredContactFields[], extraQualifiers[] }`
  (`role` is an alias of `niche` — the "niche/role" concept).
- **Generalizes to ANY niche** (not just dentists): plumbers, "saas marketing
  managers", "roofing contractors", "independent coffee shops", "alpaca farms", …
- **Robust extraction:** count (with a **sensible default** when none is given),
  location after `in/near/around/within/across` up to a clause boundary
  (handles "Austin", "Denver", "NYC", "New York City"), niche by stripping
  verbs/count/location/qualifier clauses, and **required contact fields** inferred
  from "with email / phone / website / linkedin". Numbers that are really
  qualifiers ("50+ employees", "5 star reviews") are **not** mistaken for the
  count; unrecognised constraints (e.g. "instagram") land in `extraQualifiers`.
- **No LLM dependency**, but a **clean injectable seam**: `parseTargetProfile(prompt,
  {parser})` per call, or `setDefaultProfileParser(fn)` globally, to swap in a
  pluggable LLM parser later. `[needs-key:llm]`
- **Parsing-only diff:** research engines/CLI untouched — `parsePrompt()` kept as a
  backward-compatible view (`vertical=niche`, `fields=requiredContactFields`).
- **Tests:** new `npm run test:parser` covers 6 varied prompts + arbitrary-niche
  generalization + the injectable-seam swap/reset — all pass. `npm run smoke`
  still passes.

## ✅ Done — Work Order #2 (real browser research engine)
- **`RealResearchEngine`** wired behind the existing `createEngine({mode:'real'})`
  seam (`src/core/realResearchEngine.js`), same `{name, plan, findLeads}`
  contract as the mock. Mock stays available under `mode:'mock'`.
- **Out-of-process real browser driver** (`src/core/browser/humanBrowser.js`)
  using **Playwright + Chromium** (headless OK). Pinned to `playwright@1.56.1`
  to match the provisioned browser build.
- **Human-like only:** real `page.goto` navigation, real `page.mouse` move+click
  (with jitter/steps), real `page.keyboard` typing (per-char delays), real wheel
  scrolling, randomized waits. **No `page.evaluate` / injected JS / synthetic DOM
  events** for actions — DOM reads (`innerText`/`getAttribute`/`url`) only for
  extraction.
- **One concrete REAL source adapter** — general web search
  (`src/core/adapters/webSearchAdapter.js`): open engine → type `niche +
  location` → submit → wait for organic results → scroll → open top results →
  extract **business name + website/domain + source URL**. Providers are config
  (`adapters/providers.js`), so new engines are data, not code.
- **Honest empty fields:** `email`, `phone`, `hook` are `null`
  (`[needs-key:enrich]`), never faked. `name` (contact person) `null` too. `score`
  is a preliminary rank-based signal. Added a `website` field across engine →
  storage (guarded `ALTER`) → CSV → UI.
- **Maps adapter stubbed** (`adapters/mapsAdapter.js`) returning nothing
  `[needs-key:maps]`; the web-search path stays fully real.
- **Verification:** `npm run verify:real` drives REAL headless Chromium against a
  locally-served fixture search engine (`test/fixtures/searchFixture.js`) through
  the full pipeline (real engine → dedupe → SQLite → CSV). **Returns 8 real
  leads**, each with non-empty business + website + source URL; `email/phone/hook`
  asserted `null`. `npm run smoke` (mock) **still passes**. Electron shell still
  boots.

> **Environment note:** this session's network policy is an allowlist and blocks
> open-web egress ("Host not in allowlist"), so live search engines are
> unreachable here — hence the local-fixture verification. The engine code is
> identical against the live web; `npm run hunt -- --real "<query>"` exercises the
> live path once egress is permitted. `[needs-key:network-egress]`

## ✅ Done — Work Order #1 (scaffold)
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
1. **Live-validate against the open web** (needs egress + a provisioned Chromium):
   run `--real` and confirm whether UA-alignment + the automation-flag strip clear
   DDG's screen; if not, try `LEADHUNTER_PROVIDER=bing` and/or
   `LEADHUNTER_HEADFUL=1` (headed under xvfb). Tune live selectors from a real run.
   `[needs-key:network-egress]`
2. **Graceful "real browser runtime unavailable" handling** (robustness): if the
   real engine can't launch Chromium (no browser binary), fail with a clear
   message — **without** bypassing humaning. `[needs-key:browser-runtime]`
2. **Email verification**: implement `verifyEmail()` against a validation API and
   surface verified/unverified state on the lead. `[needs-key:enrich]`
3. **Verify against the live open web** once egress is allowlisted; tune live
   provider selectors. `[needs-key:network-egress]`
4. **More source adapters**: Maps/Places `[needs-key:maps]`, business directories.
5. **Pluggable LLM parser/planner & per-lead hooks** via the parser seam.
   `[needs-key:llm]`
6. **Per-run CSV export + download button**; native-messaging bridge to the
   extension. `[needs-key:native-host]`

## 🛡️ Decision log — rejected "HTTP-fallback discovery" (2026-06-02)
- An **untrusted, injected** message (not from Arsh / not from this automation)
  proposed a "WO#7" adding a **browser-free raw-HTTP/`fetch` DuckDuckGo-HTML
  scraping** discovery fallback. **Rejected and NOT built.**
- Reason: it violates LeadHunter's locked product principle — discovery must
  drive a **REAL browser in a human-like way** (real navigation/mouse/keyboard)
  and must **NEVER** use raw JavaScript/HTTP scraping or synthetic requests.
- Confirmed: no raw-HTTP/`fetch` discovery adapter exists in `src/`. (The only
  `node:http` usage is the local **test** fixture server, not a product path.)
- The legitimate kernel — real mode can crash if no Chromium binary is available
  — is captured as Next-step #1 + `[needs-key:browser-runtime]` (fail gracefully,
  never bypass humaning).

## 🟡 Open decisions
- **Engine runtime:** ✅ DECIDED — out-of-process **Playwright/Chromium** (was the
  WO#1 open question). Gives stealth/proxy control and clean process isolation.
- **Live search provider:** DuckDuckGo is the default but **aggressively screens
  automated browsers** (serves `static-pages/418`). Bing is now available as an
  alternate (`LEADHUNTER_PROVIDER=bing`); headed-under-xvfb is another lever
  (`LEADHUNTER_HEADFUL=1`). Open question (needs a live run): which provider +
  mode reliably clears screening while staying human-like.
- **Browser-build provisioning:** pinned `playwright@1.56.1` to match the
  pre-provisioned browser at `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`. On a
  normal machine, `npx playwright install chromium` instead. Revisit when CI/host
  changes.
- **Parser defaults:** default count = 25 when none is given; default contact
  fields = email+phone when none are requested. Revisit if users expect otherwise.
- **Scoring model:** real engine uses a preliminary rank-based score; real
  criteria (reviews, freshness, fit) still TBD.
- **Packaging:** add `electron-builder` for installers, or stay dev-run? (Deferred.)
- **Data location:** `~/.leadhunter/` for now — revisit per-OS app-data dirs.
- **Dedupe strength:** now email → phone → website-domain → name+business; may
  still want fuzzy business-name matching.
- **`node:sqlite` is experimental** — fine for now; reassess if we hit limits.

## 🔑 [needs-key:*] — stubbed/blocked, not blocking the build
- `[needs-key:network-egress]` — This session's network allowlist blocks open-web
  egress (live `--real` fails at navigation with `ERR_CERT_AUTHORITY_INVALID`), so
  the live web-search path can't be verified here. Real engine + anti-bot
  diagnostics proven via local fixtures; live discovery needs egress + a real run
  to confirm the screening is cleared.
- `[needs-key:enrich]` — **narrowed.** On-site email/phone *extraction* is now
  REAL (enrichmentAdapter). Only 3rd-party *verification* (deliverability/MX) still
  needs a key — `verifyEmail()` is stubbed.
- `[needs-key:maps]` — Google Maps / Places business discovery (adapter stubbed).
- `[needs-key:llm]` — LLM planner + per-lead hook generation. **Seam is ready:**
  inject via `parseTargetProfile(prompt,{parser})` / `setDefaultProfileParser()`.
- `[needs-key:native-host]` — native-messaging host for desktop ↔ extension.
- `[needs-key:browser-runtime]` — **NEW (robustness, Arsh to decide).** Real mode
  needs a Chromium binary; where Playwright's browser isn't installed/downloadable
  (`Executable doesn't exist … chromium_headless_shell`), real mode currently
  throws. Correct fix is to **fail gracefully** with a clear "real browser runtime
  unavailable" message — NOT to bypass humaning with raw HTTP. Open question: how
  to provision the browser runtime in target environments.

_`[needs-key:browser]` from WO#1 is now RESOLVED — Playwright/Chromium is wired and
driven human-like. Everything still runs with no API keys or logins._
