#!/usr/bin/env node
'use strict';

/**
 * verify-antibot — OFFLINE proof of the WO#7 anti-detection + block-diagnostic
 * work, using local fixtures (no network egress, no keys).
 *
 *   (1) The browser's outgoing User-Agent is aligned with the REAL Chromium
 *       version (not a stale Chrome/124), and Accept-Language is sent.
 *   (2) When a provider serves an anti-bot/challenge page, discovery fails FAST
 *       with a precise diagnostic AND a `blocked` progress event — never a
 *       silent 20s selector timeout.
 *
 *   npm run verify:antibot
 */

const assert = require('node:assert');
const { startFixture } = require('./fixtures/searchFixture');
const { makeFixtureProvider } = require('../src/core/adapters/providers');
const { HumanBrowser } = require('../src/core/browser/humanBrowser');
const { RealResearchEngine } = require('../src/core/realResearchEngine');
const { chromiumAvailable } = require('./fixtures/fixtureDriver');

async function run() {
  // Anti-bot hardening is about the REAL browser's outgoing fingerprint (UA,
  // headers) and challenge-page behaviour — it can only be tested with a real
  // Chromium. In sandboxes without one, skip cleanly (green) instead of failing;
  // discover/filter/enrich logic is covered no-Chromium by verify:real/filter.
  if (!chromiumAvailable()) {
    console.log('⏭  verify:antibot SKIPPED — no Chromium present (anti-bot checks need a real browser).');
    return;
  }
  // (1) UA alignment + Accept-Language actually applied to real requests.
  const fx = await startFixture();
  const hb = new HumanBrowser({ headless: true });
  let major;
  try {
    await hb.launch();
    major = (hb.browser.version() || '').split('.')[0];
    await hb.goto(`${fx.url}/`);
  } finally {
    await hb.close();
  }
  assert.ok(fx.headers.userAgent, 'fixture should have seen a User-Agent header');
  assert.ok(
    fx.headers.userAgent.includes(`Chrome/${major}.`),
    `UA should match the real browser major (Chrome/${major}); got: ${fx.headers.userAgent}`,
  );
  assert.match(fx.headers.acceptLanguage || '', /en-US/i, 'Accept-Language header should be sent');
  console.log(`✓ UA aligned with real browser (Chrome/${major}.x) + Accept-Language "${fx.headers.acceptLanguage}"`);
  await fx.close();

  // (2) Anti-bot block page → fast, precise diagnostic + `blocked` progress event.
  const blocked = await startFixture({ block: true });
  const events = [];
  const engine = new RealResearchEngine({
    provider: makeFixtureProvider(blocked.url),
    headless: true,
    progress: (phase, message, data) => events.push({ phase, message, data }),
  });

  let threw = null;
  const t0 = Date.now();
  try {
    await engine.findLeads('find 10 dentists in Austin with email and phone', { limit: 5 });
  } catch (err) {
    threw = err;
  }
  const elapsed = Date.now() - t0;
  await blocked.close();

  assert.ok(threw, 'blocked discovery should throw a clear error (not return silently)');
  assert.match(threw.message, /blocked|screened|challenge/i, `diagnostic should name the block: ${threw && threw.message}`);
  const blockEvt = events.find((e) => e.phase === 'blocked');
  assert.ok(blockEvt, 'a "blocked" progress event should fire (only after ALL providers fail)');
  assert.match(blockEvt.message, /blocked|screened|challenge/i, 'blocked event should carry the diagnostic');
  assert.match(blockEvt.data && blockEvt.data.url ? blockEvt.data.url : '', /static-pages\/418/, 'blocked event should name the challenge URL');
  assert.ok(elapsed < 15000, `should fail fast, not wait out a silent 20s timeout (took ${elapsed}ms)`);
  console.log(`✓ anti-bot block detected fast (${elapsed}ms), with a "blocked" progress event after the chain exhausted`);
  console.log(`  diagnostic: ${threw.message}`);

  console.log('\nAll anti-bot checks passed. ✅');
}

run().catch((err) => {
  console.error('\n❌ Anti-bot verification failed:', err.stack || err.message);
  process.exit(1);
});
