#!/usr/bin/env node
'use strict';

/**
 * parser.test — unit tests for the deterministic prompt → TargetProfile parser.
 * Covers varied niches/roles, locations, counts, contact fields and qualifiers,
 * plus the no-count default and the injectable LLM seam. Exits non-zero on the
 * first failed assertion.
 *
 *   npm run test:parser
 */

const assert = require('node:assert');
const {
  parseTargetProfile,
  ruleBasedTargetProfile,
  setDefaultProfileParser,
  DEFAULT_COUNT,
} = require('../src/core/promptParser');

const sortF = (a) => [...a].sort();

const CASES = [
  {
    prompt: 'find 50 dentists in Austin with email and phone',
    expect: { niche: 'dentists', location: 'Austin', count: 50, fields: ['email', 'phone'], extra: [] },
  },
  {
    prompt: 'get 20 plumbers near Denver with a website',
    expect: { niche: 'plumbers', location: 'Denver', count: 20, fields: ['website'], extra: [] },
  },
  {
    prompt: '100 SaaS marketing managers in NYC with LinkedIn',
    expect: { niche: 'saas marketing managers', location: 'NYC', count: 100, fields: ['linkedin'], extra: [] },
  },
  {
    // No count → sensible default; no contact phrase → default email+phone.
    prompt: 'find roofing contractors in Miami',
    expect: { niche: 'roofing contractors', location: 'Miami', count: DEFAULT_COUNT, fields: ['email', 'phone'], extra: [] },
  },
  {
    // A leading-looking number that is actually a qualifier ("50+ employees").
    prompt: 'get yoga studios in Portland with 50+ employees and email',
    expect: { niche: 'yoga studios', location: 'Portland', count: DEFAULT_COUNT, fields: ['email'], extra: ['50+ employees'] },
  },
  {
    // Multi-word niche, multi-field, and a non-contact qualifier (instagram).
    prompt: 'find independent coffee shops near Seattle with phone, website and instagram',
    expect: { niche: 'independent coffee shops', location: 'Seattle', count: DEFAULT_COUNT, fields: ['phone', 'website'], extra: ['instagram'] },
  },
];

function run() {
  for (const { prompt, expect } of CASES) {
    const p = parseTargetProfile(prompt);
    assert.strictEqual(p.niche, expect.niche, `niche for: ${prompt}`);
    assert.strictEqual(p.role, expect.niche, `role alias for: ${prompt}`);
    assert.strictEqual(p.location, expect.location, `location for: ${prompt}`);
    assert.strictEqual(p.count, expect.count, `count for: ${prompt}`);
    assert.deepStrictEqual(sortF(p.requiredContactFields), sortF(expect.fields), `fields for: ${prompt}`);
    assert.deepStrictEqual(p.extraQualifiers, expect.extra, `qualifiers for: ${prompt}`);
    console.log(
      `✓ ${prompt}\n    → niche="${p.niche}" location=${JSON.stringify(p.location)} count=${p.count} ` +
        `fields=[${p.requiredContactFields}] extra=[${p.extraQualifiers}]`,
    );
  }

  // Generalization: a niche the parser has never been tuned for.
  const exotic = parseTargetProfile('find 7 alpaca farms in Vermont with email');
  assert.strictEqual(exotic.niche, 'alpaca farms');
  assert.strictEqual(exotic.location, 'Vermont');
  assert.strictEqual(exotic.count, 7);
  console.log('✓ generalizes to arbitrary niches (alpaca farms)');

  // Injectable LLM seam: a custom parser is used in place of the rule-based one.
  let called = false;
  setDefaultProfileParser((prompt) => {
    called = true;
    return { ...ruleBasedTargetProfile(prompt), niche: 'INJECTED' };
  });
  const injected = parseTargetProfile('find 5 dentists in Austin');
  assert.ok(called, 'injected parser should be invoked [needs-key:llm seam]');
  assert.strictEqual(injected.niche, 'INJECTED', 'injected parser output should be used');
  setDefaultProfileParser(); // reset
  const reset = parseTargetProfile('find 5 dentists in Austin');
  assert.strictEqual(reset.niche, 'dentists', 'reset should restore the rule-based parser');
  console.log('✓ injectable LLM parser seam works (and resets)');

  console.log('\nAll parser tests passed. ✅');
}

run();
