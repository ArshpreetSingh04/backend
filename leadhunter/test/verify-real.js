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

const PROMPT = 'find 50 dentists in Austin with email and phone';

async function run() {
  const fixture = await startFixture();
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'leadhunter-real-'));
  const dbPath = path.join(dataDir, 'leadhunter.db');
  const csvPath = path.join(dataDir, 'leads.csv');

  console.log(`Fixture search engine: ${fixture.url}`);
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
    const result = await runLeadHunt(PROMPT, {
      mode: 'real',
      provider: makeFixtureProvider(fixture.url),
      headless: true,
      maxResults: 5,
      dataDir,
      dbPath,
      csvPath,
    });

    const leads = result.leads;

    // --- assertions -------------------------------------------------------
    assert.strictEqual(result.engine, 'real', 'engine should be the real one');
    assert.ok(leads.length >= 3, `expected >= 3 real leads, got ${leads.length}`);

    for (const l of leads) {
      assert.ok(l.business && l.business.trim(), 'business name must be non-empty');
      assert.ok(l.website && l.website.trim(), 'website/domain must be non-empty');
      assert.ok(l.source && /^https?:\/\//.test(l.source), 'source must be a real URL');
      // Not yet enriched — must be empty, never faked.
      assert.strictEqual(l.email, null, 'email should be null [needs-key:enrich]');
      assert.strictEqual(l.phone, null, 'phone should be null [needs-key:enrich]');
      assert.strictEqual(l.hook, null, 'hook should be null [needs-key:enrich]');
    }
    console.log(`✓ ${leads.length} REAL leads, each with non-empty business + website + source URL`);

    // Scoring reflects requiredContactFields: email+phone required but unobtainable
    // (no enrichment) → every lead down-ranked below its rank-1 base of 100.
    // Rank-1 base 100 − 12×2 = 76.
    assert.strictEqual(leads[0].score, 76, 'rank-1 lead down-ranked to 76 for missing email+phone');
    assert.ok(leads.every((l) => l.score <= 76), 'all leads down-ranked by required fields');
    console.log('✓ scoring folds in requiredContactFields end-to-end (rank-1 = 76, not 100)');

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
