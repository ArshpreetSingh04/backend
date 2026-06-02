#!/usr/bin/env node
'use strict';

/**
 * verify-filter — OFFLINE proof that real-mode discovery keeps actual business
 * sites and drops ad redirects + directory/aggregator pages. Drives a REAL
 * browser against a fixture whose SERP mixes junk above real businesses
 * (mirroring a live "dentists in Austin" run). No network, no keys.
 *
 *   npm run verify:filter
 */

const assert = require('node:assert');
const { startFixture, JUNK, BUSINESSES, rank } = require('./fixtures/searchFixture');
const { makeFixtureProvider } = require('../src/core/adapters/providers');
const { isAdLink, isExcludedDomain } = require('../src/core/adapters/webSearchAdapter');
const { RealResearchEngine } = require('../src/core/realResearchEngine');
const { FixtureDriver, chromiumAvailable } = require('./fixtures/fixtureDriver');

// Real Chromium when present; otherwise the no-Chromium fixture driver double.
const REAL_BROWSER = chromiumAvailable();
const browserFactory = REAL_BROWSER ? undefined : (o) => new FixtureDriver(o);

const PROMPT = 'find 20 dentists in Austin with email and phone';
const QUERY = 'dentists Austin';

async function run() {
  // --- fast pure-function classification (the exact live examples) ----------
  assert.ok(isAdLink('https://duckduckgo.com/y.js?ad_domain=saintsdental.com&ad_provider=bingv7aa'), 'DDG /y.js ad');
  assert.ok(isAdLink('https://www.bing.com/aclick?ld=abc'), 'Bing /aclick ad');
  assert.ok(!isAdLink('https://austinsmiles.example.com/'), 'real site is not an ad');
  for (const d of ['yelp.com', 'www.zocdoc.com', 'opencare.com', 'statesman.com', 'facebook.com', 'duckduckgo.com']) {
    assert.ok(isExcludedDomain(d), `${d} should be excluded`);
  }
  for (const d of ['austinsmiles.example.com', 'lonestardental.example.com']) {
    assert.ok(!isExcludedDomain(d), `${d} should be kept`);
  }
  console.log('✓ ad/aggregator classifiers match the live-run examples');

  // --- end-to-end against a junk-laden fixture ------------------------------
  const fx = await startFixture({ withJunk: true });

  // BEFORE: the raw SERP order this fixture serves for the query.
  const serp = rank([...JUNK, ...BUSINESSES], QUERY);
  console.log('\nBEFORE — raw SERP results (what a naive engine would scrape):');
  for (const r of serp) {
    const tag = r.kind === 'ad' ? 'AD' : r.kind === 'aggregator' ? 'AGGREGATOR' : 'business';
    const target = r.kind === 'ad' ? r.adHref : r.domain;
    console.log(`  [${tag.padEnd(10)}] ${r.name}  →  ${target}`);
  }

  console.log(`\nDriver: ${REAL_BROWSER ? 'real Chromium (HumanBrowser)' : 'no-Chromium fixture driver (test double)'}`);
  const engine = new RealResearchEngine({ provider: makeFixtureProvider(fx.url), headless: true, browserFactory });
  let leads;
  try {
    leads = await engine.findLeads(PROMPT, { limit: 20 });
  } finally {
    await fx.close();
  }

  console.log('\nAFTER — leads that survived filtering:');
  for (const l of leads) console.log(`  [business  ] ${l.business}  →  ${l.website}`);

  // Assertions: no ads, no aggregators; the real dentists survived.
  for (const l of leads) {
    assert.ok(!isExcludedDomain(l.website), `aggregator leaked through: ${l.website}`);
    assert.ok(!/duckduckgo\.com|y\.js|\baclick\b/i.test(l.source), `ad/redirect leaked through: ${l.source}`);
    assert.ok(!/duckduckgo\.com/i.test(l.website), `search-engine host leaked as website: ${l.website}`);
  }
  const names = leads.map((l) => l.business);
  assert.ok(!names.some((n) => /saints dental/i.test(n)), 'the ad ("Saints Dental") must not appear as a lead');
  assert.ok(!names.some((n) => /yelp|zocdoc|opencare/i.test(n)), 'no directory titles as leads');
  const survivingHosts = leads.map((l) => l.website);
  for (const expected of ['austinsmiles.example.com', 'lonestardental.example.com', 'congressdentistry.example.com']) {
    assert.ok(survivingHosts.includes(expected), `real business ${expected} should survive`);
  }
  assert.ok(leads.length >= 6, `expected the real Austin dentists to survive, got ${leads.length}`);

  console.log(`\n✓ dropped ${serp.length - leads.length} ad/aggregator results; kept ${leads.length} real businesses`);
  console.log('\nAll ad/aggregator filtering checks passed. ✅');
}

run().catch((err) => {
  console.error('\n❌ Filter verification failed:', err.stack || err.message);
  process.exit(1);
});
