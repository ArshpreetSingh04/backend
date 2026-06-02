#!/usr/bin/env node
'use strict';

/**
 * Headless CLI runner — same pipeline the desktop app uses, no GUI required.
 * Handy for verification and for running hunts from scripts/cron later.
 *
 *   node src/cli.js "find 50 dentists in Austin with email and phone"
 */

const { runLeadHunt } = require('./core/pipeline');

async function main() {
  const args = process.argv.slice(2);
  const real = args.includes('--real'); // drive a real browser (live web)
  const prompt = args.filter((a) => !a.startsWith('--')).join(' ').trim()
    || 'find 50 dentists in Austin with email and phone';
  const mode = real ? 'real' : 'mock';

  console.log(`\n🎯 LeadHunter [${mode}] — "${prompt}"\n`);
  if (real) {
    console.log('Note: --real hits the live open web. In a sandbox with an egress');
    console.log('allowlist this may fail; use `npm run verify:real` for a local proof.\n');
  }

  const result = await runLeadHunt(prompt, { mode });

  console.log('Plan:', JSON.stringify({
    count: result.plan.count,
    vertical: result.plan.vertical,
    location: result.plan.location,
    fields: result.plan.fields,
  }));
  console.log(`Engine: ${result.engine}\n`);

  console.table(result.leads.map((l) => ({
    name: l.name,
    business: l.business,
    website: l.website,
    email: l.email,
    phone: l.phone,
    source: l.source,
    score: l.score,
  })));

  console.log(`\nFound ${result.stats.found}, saved ${result.stats.inserted} new (${result.stats.skipped} dupes skipped).`);
  console.log(`DB:  ${result.dbPath}`);
  console.log(`CSV: ${result.csvPath}\n`);
}

main().catch((err) => {
  console.error('LeadHunter failed:', err.message);
  process.exit(1);
});
