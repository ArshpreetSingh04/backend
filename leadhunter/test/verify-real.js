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
