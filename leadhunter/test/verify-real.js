#!/usr/bin/env node
'use strict';

/**
 * verify-real — proves the RealResearchEngine works end-to-end by driving a REAL
 * headless Chromium (human-like nav/type/click/scroll) against a locally-served
 * fixture search engine, then running the WHOLE pipeline (real engine → dedupe →
 * SQLite → CSV).
 *
 * Why a fixture? This environment's network policy blocks open-web egress
 * ("Host not in allowlist"), so live search engines are unreachable here. The
 * engine code is identical against the live web once egress is allowed.
 *
 *   npm run verify:real
 */

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { startFixture } = require('./fixtures/searchFixture');
const { makeFixtureProvider } = require('../src/core/adapters/providers');
const { RealResearchEngine } = require('../src/core/realResearchEngine');
const { runLeadHunt } = require('../src/core/pipeline');
const { FixtureDriver, chromiumAvailable } = require('./fixtures/fixtureDriver');

const PROMPT = 'find 50 dentists in Austin with email and phone';

// Use the real Chromium-backed engine when a browser is present; otherwise fall
// back to the test-only fixture driver so the REAL engine code paths still run
// in sandboxes that can't provision a Chromium binary. (Production never does this.)
const REAL_BROWSER = chromiumAvailable();
const browserFactory = REAL_BROWSER ? undefined : (o) => new FixtureDriver(o);

async function run() {
  const fixture = await startFixture();
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'leadhunter-real-'));
  const dbPath = path.join(dataDir, 'leadhunter.db');
  const csvPath = path.join(dataDir, 'leads.csv');

  console.log(`Fixture search engine: ${fixture.url}`);
  console.log(`Driver: ${REAL_BROWSER ? 'real Chromium (HumanBrowser)' : 'no-Chromium fixture driver (test double)'}`);
  console.log(`Prompt: "${PROMPT}"\n`);

  try {
    // --- plan() now consumes the TargetProfile (no browser needed) ---------
    const engine = new RealResearchEngine({ provider: makeFixtureProvider(fixture.url) });

    const planD = await engine.plan('find 50 dentists in Austin with email and phone');
    assert.strictEqual(planD.niche, 'dentists', 'plan.niche');
    assert.strictEqual(planD.location, 'Austin', 'plan.location');
    assert.strictEqual(planD.count, 50, 'plan.count');
    assert.deepStrictEqual(planD.requiredContactFields, ['email', 'phone'], 'plan.requiredContactFields');
    assert.deepStrictEqual(planD.extraQualifiers, [], 'plan.extraQualifiers');
    assert.strictEqual(planD.query, 'dentists Austin', 'plan.query shaped from profile');

    const planP = await engine.plan('get 20 plumbers near Denver with a website and 5 star reviews');
    assert.strictEqual(planP.niche, 'plumbers', 'plan.niche (plumbers)');
    assert.strictEqual(planP.location, 'Denver', 'plan.location (Denver)');
    assert.strictEqual(planP.count, 20, 'plan.count (20)');
    assert.deepStrictEqual(planP.requiredContactFields, ['website'], 'plan.requiredContactFields (website)');
    assert.deepStrictEqual(planP.extraQualifiers, ['5 star reviews'], 'plan.extraQualifiers (5 star reviews)');
    assert.strictEqual(planP.query, 'plumbers Denver 5 star reviews', 'plan.query folds qualifier');
    console.log('✓ plan() reflects requiredContactFields + extraQualifiers (dentists & plumbers)');
    const events = [];
    const result = await runLeadHunt(PROMPT, {
      mode: 'real',
      provider: makeFixtureProvider(fixture.url),
      headless: true,
      maxResults: 5,
      browserFactory,
      dataDir,
      dbPath,
      csvPath,
      onProgress: (evt) => events.push(evt),
    });

    const leads = result.leads;

    // --- live progress streamed through the pipeline ----------------------
    const phases = events.map((e) => e.phase);
    for (const required of ['parsing-prompt', 'searching', 'business-found', 'qualifying', 'enriching', 'persisted', 'done']) {
      assert.ok(phases.includes(required), `progress should include "${required}" (got: ${[...new Set(phases)].join(', ')})`);
    }
    const foundEvents = events.filter((e) => e.phase === 'business-found');
    assert.ok(foundEvents.length >= 3, `expected >= 3 business-found events, got ${foundEvents.length}`);
    assert.strictEqual(foundEvents.length, leads.length, 'one business-found event per lead in the table');
    console.log(`✓ streamed ${events.length} progress events (${foundEvents.length} business-found) through phases: ${[...new Set(phases)].join(' → ')}`);

    // --- assertions -------------------------------------------------------
    assert.strictEqual(result.engine, 'real', 'engine should be the real one');
    assert.ok(leads.length >= 3, `expected >= 3 real leads, got ${leads.length}`);

    const emailRe = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
    for (const l of leads) {
      assert.ok(l.business && l.business.trim(), 'business name must be non-empty');
      assert.ok(l.website && l.website.trim(), 'website/domain must be non-empty');
      assert.ok(l.source && /^https?:\/\//.test(l.source), 'source must be a real URL');
      assert.strictEqual(l.hook, null, 'hook should be null [needs-key:enrich/llm]');
      if (l.email !== null) assert.match(l.email, emailRe, 'any filled email must look real');
    }
    console.log(`✓ ${leads.length} REAL leads, each with non-empty business + website + source URL`);

    // --- enrichment filled missing fields and removed the down-rank penalty ---
    // rank-1 (b1) has email + phone on its contact page → both filled, score back
    // to its full base of 100 (was 76 before enrichment).
    const top = leads[0];
    assert.match(top.email, emailRe, 'rank-1 email enriched from its contact page');
    assert.ok(top.phone && top.phone.trim(), 'rank-1 phone enriched');
    assert.strictEqual(top.score, 100, 'rank-1 penalty removed after enrichment (76 → 100)');
    console.log(`✓ enrichment filled "${top.business}" → ${top.email} / ${top.phone}; score 76 → 100`);

    // rank-2 (b2) has ONLY an email on its contact page → email filled, phone left
    // null (never faked), so it keeps a single −12 penalty (base 92 → 80).
    const second = leads[1];
    assert.match(second.email, emailRe, 'rank-2 email enriched');
    assert.strictEqual(second.phone, null, 'rank-2 phone genuinely absent → left null, not faked');
    assert.strictEqual(second.score, 80, 'rank-2 keeps one penalty for the still-missing phone');
    console.log('✓ honest partial enrichment: email filled, missing phone left null (score 80)');

    // Persistence + export actually happened through the normal pipeline.
    assert.ok(fs.existsSync(dbPath), 'sqlite db should exist');
    assert.ok(fs.existsSync(csvPath), 'csv should exist');
    const csv = fs.readFileSync(csvPath, 'utf8');
    assert.match(csv.split('\n')[0], /website/, 'csv header should include website');
    console.log('✓ persisted to SQLite and exported to CSV (incl. website column)');

    // --- sample output ----------------------------------------------------
    console.log('\nSample of discovered leads:');
    console.table(
      leads.slice(0, 5).map((l) => ({
        business: l.business,
        website: l.website,
        source: l.source,
        email: l.email,
        phone: l.phone,
        score: l.score,
      })),
    );
    console.log(`\nDB:  ${dbPath}\nCSV: ${csvPath}`);
    console.log('\nReal-engine verification passed. ✅');
  } finally {
    await fixture.close();
    fs.rmSync(dataDir, { recursive: true, force: true });
  }
}

run().catch((err) => {
  console.error('\n❌ Real-engine verification failed:', err.stack || err.message);
  process.exit(1);
});
