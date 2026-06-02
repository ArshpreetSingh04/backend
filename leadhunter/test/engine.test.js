#!/usr/bin/env node
'use strict';

/**
 * engine.test — OFFLINE unit tests (no browser, no network) for the real
 * engine's TargetProfile-driven query shaping and qualify/scoring step.
 *
 *   npm run test:engine
 */

const assert = require('node:assert');
const { parseTargetProfile } = require('../src/core/promptParser');
const { buildQuery, qualifyLeads } = require('../src/core/realResearchEngine');

function run() {
  // --- query shaping uses niche + location + extra qualifiers --------------
  const pDentists = parseTargetProfile('find 50 dentists in Austin with email and phone');
  assert.strictEqual(buildQuery(pDentists), 'dentists Austin', 'dentists query');

  const pPlumbers = parseTargetProfile('get 20 plumbers near Denver with a website and 5 star reviews');
  assert.strictEqual(buildQuery(pPlumbers), 'plumbers Denver 5 star reviews', 'plumbers query folds qualifier');
  console.log('✓ buildQuery shapes from niche + location + extraQualifiers');

  // Synthetic discoveries (what the browser would hand back).
  const discoveries = [
    { business: 'Austin Smiles Family Dental', website: 'austinsmiles.example.com', source: 'http://x/1', rank: 1 },
    { business: 'Zilker Orthodontics & Dental', website: 'zilkerortho.example.com', source: 'http://x/2', rank: 2 },
    { business: 'No Website Co', website: '', source: 'http://x/3', rank: 3 }, // not a usable lead
  ];

  // --- requiredContactFields fold into the score (down-rank, never faked) ---
  const dentistLeads = qualifyLeads(discoveries, pDentists); // requires email+phone (both unobtainable)
  assert.strictEqual(dentistLeads.length, 2, 'no-website discovery dropped; 2 real leads remain');
  // base 100 / 92, minus 12 per missing required field (email, phone) = -24
  assert.strictEqual(dentistLeads[0].score, 76, 'rank-1 down-ranked for missing email+phone');
  assert.strictEqual(dentistLeads[1].score, 68, 'rank-2 down-ranked for missing email+phone');
  for (const l of dentistLeads) {
    assert.strictEqual(l.email, null, 'email stays null [needs-key:enrich]');
    assert.strictEqual(l.phone, null, 'phone stays null [needs-key:enrich]');
  }
  console.log('✓ requiredContactFields [email,phone] down-rank leads (76, 68), never faked');

  // --- website requirement is satisfiable now; extraQualifier boosts score --
  const pWeb = parseTargetProfile('get dental clinics in Austin with a website and orthodontics');
  assert.deepStrictEqual(pWeb.requiredContactFields, ['website'], 'website required');
  assert.deepStrictEqual(pWeb.extraQualifiers, ['orthodontics'], 'orthodontics is an extra qualifier');

  const webLeads = qualifyLeads(discoveries, pWeb);
  assert.strictEqual(webLeads.length, 2, 'leads with a website qualify; no-website dropped');
  assert.strictEqual(webLeads[0].score, 100, 'rank-1 keeps full base (website present, no qualifier match)');
  assert.strictEqual(webLeads[1].score, 98, 'rank-2 boosted +6 by matching "orthodontics" qualifier');
  console.log('✓ website requirement qualifies; matching extraQualifier boosts score (+6)');

  // --- a required, verifiable field that is genuinely missing → dropped -----
  const onlyNoSite = qualifyLeads(
    [{ business: 'No Website Co', website: '', source: 'http://x/3', rank: 1 }],
    pWeb,
  );
  assert.strictEqual(onlyNoSite.length, 0, 'lead missing required website is dropped');
  console.log('✓ lead missing a required, verifiable field (website) is dropped');

  console.log('\nAll engine tests passed. ✅');
}

run();
