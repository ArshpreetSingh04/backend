# LeadHunter — PROGRESS

_Updated 2026-06-02. Work Order #10 — direct results-URL navigation + provider fallback chain._

## ✅ Done — Work Order #10 (live discovery via direct results URL + Bing→DDG fallback)
Grounded in a real live run (full Chromium build, headless, Chrome/141 UA, working
egress):
- **Corrects the WO#8 note:** the DDG **418 DOES reproduce headless with the full
  Chromium build** — it is NOT a headless-shell artifact. The homepage → type →
  press-Enter interaction is what trips DDG's screen: it redirects to
  `static-pages/418.html`. `html.duckduckgo.com` is blocked the same way.
- **Bing's type→Enter also fails** (Enter never submits; the page sits on the
  autocomplete dropdown, so `#b_results .b_algo` times out). But **navigating the
  real browser DIRECTLY to `https://www.bing.com/search?q=…` returns 10 real
  organic `.b_algo` results in ~2s, headless, no block.**
- **Fix (still real, human-like navigation — never raw HTTP):**
  - `webSearchAdapter` now navigates **directly to the provider's results URL**
    (`provider.searchUrl(query)`) instead of homepage→type→Enter — dropping the
    interaction that gets us screened (DDG) or stuck (Bing).
  - **Provider fallback chain**: try each provider's results URL in order; if one
    serves a 418/challenge or yields zero usable businesses, fall through to the
    next. Only emit `blocked` (and throw) if **all** providers fail.
  - **Bing is the primary** live provider; **DuckDuckGo stays as fallback** (may
    work headed / from a residential IP). Chain = `[bing, duckduckgo]`.
  - Bing result links are `/ck/a?` redirect wrappers, so the true business domain
    is taken from the **landed `page.url()`** after the real click-through, and the
    ad/aggregator denylist runs on that **resolved host** (unchanged click-through
    approach).
  - Geo: Bing results URL adds `cc=US&setlang=en-US`; the location term in the
    query also drives geo (sandbox IPs can be anywhere — flagged by the live run).
- **Scope:** changes are in `webSearchAdapter.js` + `providers.js` (plus a minimal
  provider-chain wiring in `realResearchEngine.js`). The offline `fixtureDriver`
  path and the `browserFactory` injection seam were **not** touched.
- **Verified:** `verify:real` + `verify:filter` stay green **both** with Chromium
  and with none (fixture driver) — the fixture provider now uses a `searchUrl`.
  `verify:antibot` confirms the chain → `blocked` diagnostic fires fast (~0.8s)
  only after the chain is exhausted. (Live Bing couldn't be exercised in *this*
  sandbox — egress is 403 here — but the Bing→DDG fallback wiring was confirmed
  end-to-end, and live Bing success is per the grounded run above.)

## ✅ Done — Work Order #9 (no-Chromium fixture driver restores offline proofs)
Grounded in a fresh clean-sandbox run of this branch: `npm install` is clean, but
**a Chromium binary cannot be provisioned** — `npx playwright install chromium`
hangs at "0% of 175.9 MiB" because the Playwright CDN is **blocked by the egress
allowlist**. So in a clean sandbox `--real`, `verify:real`, `verify:filter`,
`verify:antibot` all died at `browserType.launch` (even `verify:real`, which only
targets the local 127.0.0.1 fixture — the HTTP server starts fine; the *browser*
launch is what fails). Only mock (`smoke`, `test:parser`) ran. The WO#8 launch fix
doesn't rescue a clean checkout (nothing to point `executablePath` at). This left
the "demonstrable without keys/browser" methodology **blind** to the real engine.
- **Injectable browser-driver seam** (`realResearchEngine.js`): `findLeads()` now
  builds its driver via `makeBrowser()`, which uses an injected `browserFactory`
  if provided, else the real `HumanBrowser`. Threaded through the pipeline.
  **Production is untouched** — `--real` (CLI/app) never injects, so it always
  gets real `HumanBrowser`+Chromium.
- **Test-only no-Chromium driver** (`test/fixtures/fixtureDriver.js`): implements
  the exact surface the adapters use (`goto/type/pressEnter/click/scroll/settle/
  back` + `page.locator/getByRole/url/title/waitForSelector` + locator
  `first/nth/count/innerText/getAttribute`), backed by the existing search
  fixture's **real HTML** parsed with `node-html-parser` (dev dep). The REAL
  discover → ad/aggregator filter → qualify → enrich → dedupe code runs
  **unchanged** against it. It is **never** wired into `--real` and is **not** a
  raw-HTTP discovery path — it only loads our own 127.0.0.1 fixture.
- **Auto-detect**: `verify:real` / `verify:filter` use real Chromium when a binary
  is present, else fall back to the fixture driver (`chromiumAvailable()`).
  `verify:antibot` (which tests the *real browser's* UA/fingerprint) **skips
  cleanly** when no Chromium is present.
- **Verified BOTH ways:** with no Chromium (`PLAYWRIGHT_BROWSERS_PATH` → empty),
  `verify:real` returns the 8 real leads with enrichment (b1 76→100; b2 partial
  80) and `verify:filter` drops all 4 ad/aggregator results and keeps 8 real
  businesses — `smoke`, `test:parser`, `test:engine`, `verify:antibot` (skip) all
  green. With Chromium present, the real-browser path still passes unchanged.

## ✅ Done — Work Order #8 (real leads, not ads/directories + full-Chromium launch)
Grounded in a real live run (Arsh provisioned the full Chromium build and ran
`--real` against LIVE DuckDuckGo for "dentists in Austin"):
- **The WO#7 anti-bot 418 premise did NOT reproduce.** Driving the **full**
  Chromium (headless=new), DDG rendered the SERP and `[data-testid="result"]` in
  ~3.4s with 19 organic links — the 418 block was an artifact of the headless-
  **shell** binary / no-egress sandbox, not DDG genuinely screening us. Real
  discovery basically works once a real browser launches.
  - **⚠️ CORRECTED by WO#10:** the 418 **does** reproduce with the full Chromium
    build too — it's triggered by the homepage → type → **press-Enter** flow, not
    the binary. WO#10 switches to direct results-URL navigation (no Enter) and
    makes Bing the primary provider. (The ~3.4s success above was likely an
    already-warm session; the type→Enter submit is what DDG screens.)
- **THE REAL BUG (this increment): discovery returned ads + directories, not
  businesses.** Top results for the live query were a DDG `/y.js` **ad redirect**
  (host → duckduckgo.com) and aggregator pages (Yelp, Zocdoc, Opencare, a
  Statesman listicle) — which the engine turned into junk "leads" (directory
  titles + directory domains).
  - **Fix (smarter SERP reading, still human-like — never raw HTTP)**
    (`webSearchAdapter.js`): drop **ad/redirect** links by href
    (`/y.js`, `/aclick`, `/aclk`, `ad_domain=`, …) before opening them, and drop
    **directory/aggregator/search-engine domains** by a denylist (yelp, zocdoc,
    opencare, yellowpages, healthgrades, mapquest, facebook, linkedin, tripadvisor,
    statesman, duckduckgo/bing/google, …). Discovery now **keeps scanning past
    junk** until it has up to `maxResults` real business homepages.
- **Launch portability fix folded in** (`humanBrowser.js`): prefer the **full
  Chromium build** via `executablePath` (`chromium.executablePath()`), with a
  `LEADHUNTER_CHROMIUM_PATH` override, so real mode launches **without** the
  separate `chromium_headless_shell` binary (which isn't always installable). On
  failure it throws a clear **"real browser runtime unavailable"** message — it
  never falls back to raw HTTP.
- **Verified OFFLINE** (no egress here): new `npm run verify:filter` drives a REAL
  browser against a junk-laden fixture (ad + Yelp/Zocdoc/Opencare above the real
  dentists) and shows **before → after**: all **4 junk results dropped**, all **8
  real businesses kept**; pure classifiers also match the exact live examples.
  `smoke`, `test:engine`, `test:parser`, `verify:real`, `verify:antibot` all still
  pass.

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
1. **Live end-to-end run on Bing** (needs egress + Chromium): run `--real` and
   confirm the direct results-URL + click-through yields real business homepages
   (not `/ck/a` wrappers or aggregators), tune `.b_algo` selectors + the denylist
   from the real SERP, and verify the `cc`/location geo actually returns local
   results. `[needs-key:network-egress]` `[needs-key:browser-runtime]`
2. **Bing geo from the query's location** (replace the hardcoded `cc=US` with a
   region derived from the parsed location) once the live run shows what's needed.
2. **Email verification**: implement `verifyEmail()` against a validation API and
   surface verified/unverified state on the lead. `[needs-key:enrich]`
3. **More source adapters**: Maps/Places `[needs-key:maps]`, business directories.
4. **Pluggable LLM parser/planner & per-lead hooks** via the parser seam.
   `[needs-key:llm]`
5. **Per-run CSV export + download button**; native-messaging bridge to the
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
- **Live search provider:** ✅ DECIDED (WO#10) — **Bing primary, DuckDuckGo
  fallback**, reached via **direct results-URL navigation** (no homepage→type→
  Enter, which DDG screens with a 418 and Bing fails to submit). The fallback
  chain auto-advances and only reports `blocked` if all providers fail. Open: tune
  Bing selectors/geo from a live run; DDG may still serve headed/residential.
- **Ad/aggregator denylist:** maintained in `webSearchAdapter.js`
  (`EXCLUDED_DOMAINS` + `AD_LINK_RE`). Judgment call on coverage; revisit/tune
  from real SERPs. Open option: follow a directory result to its underlying
  business domains (kept out for now to stay small).
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
- **Test-only browser double:** `fixtureDriver` (+ `node-html-parser` dev dep) is
  the offline substitute for the real browser in verify scripts. It must never
  leak into production (`browserFactory` is only injected by tests). Keep its
  surface in lock-step with what the adapters consume from HumanBrowser/Page.

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
- `[needs-key:browser-runtime]` — **a clean sandbox cannot provision Chromium**:
  `npx playwright install chromium` is blocked by the egress allowlist (Playwright
  CDN), so **live browser proofs (`--real`, real-Chromium verify runs) cannot run
  here at all**. WO#8 prefers the full Chromium build + fails gracefully, but that
  only helps when a binary already exists. **Offline substitute (WO#9):** the
  test-only `fixtureDriver` runs the real engine's selection/extraction/enrich/
  dedupe logic against real fixture HTML with no Chromium. Still open for Arsh:
  how to provision a Chromium binary in restricted target environments (vendored
  binary? allowlist the CDN? system Chrome via `LEADHUNTER_CHROMIUM_PATH`?).

_`[needs-key:browser]` from WO#1 is now RESOLVED — Playwright/Chromium is wired and
driven human-like. Everything still runs with no API keys or logins._
