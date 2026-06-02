#!/usr/bin/env node
'use strict';

/**
 * Smoke test — exercises the whole pipeline (parse -> mock research -> dedupe ->
 * SQLite -> CSV) in a throwaway temp dir, with zero GUI and zero external deps.
 * Exits non-zero on the first failed assertion.
 */

const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { runLeadHunt } = require('../src/core/pipeline');
const { parsePrompt } = require('../src/core/promptParser');
const { LeadStore } = require('../src/core/storage');

async function run() {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'leadhunter-smoke-'));
  const dbPath = path.join(dataDir, 'leadhunter.db');
  const csvPath = path.join(dataDir, 'leads.csv');

  // 1) Prompt parsing
  const plan = parsePrompt('find 50 dentists in Austin with email and phone');
  assert.strictEqual(plan.count, 50, 'count should parse to 50');
  assert.strictEqual(plan.vertical, 'dentists', 'vertical should be dentists');
  assert.strictEqual(plan.location, 'Austin', 'location should be Austin');
  assert.deepStrictEqual([...plan.fields].sort(), ['email', 'phone'], 'fields should be email+phone');
  console.log('✓ prompt parsing');

  // 2) Full pipeline run
  const result = await runLeadHunt('find 50 dentists in Austin with email and phone', { dataDir, dbPath, csvPath });
  assert.strictEqual(result.leads.length, 5, 'should return 5 mock leads');
  for (const l of result.leads) {
    for (const k of ['name', 'business', 'email', 'phone', 'source', 'hook', 'score']) {
      assert.ok(l[k] !== undefined && l[k] !== null && l[k] !== '', `lead.${k} should be set`);
    }
  }
  assert.strictEqual(result.stats.inserted, 5, 'should insert 5 leads first run');
  console.log('✓ pipeline returns 5 complete leads');

  // 3) Persistence
  assert.ok(fs.existsSync(dbPath), 'sqlite db should exist');
  const store = new LeadStore(dbPath);
  assert.strictEqual(store.allLeads().length, 5, 'db should hold 5 leads');
  store.close();
  console.log('✓ leads persisted to SQLite');

  // 4) CSV export
  assert.ok(fs.existsSync(csvPath), 'csv should exist');
  const csv = fs.readFileSync(csvPath, 'utf8');
  const rows = csv.trim().split('\n');
  assert.strictEqual(rows.length, 6, 'csv should have header + 5 rows');
  assert.match(rows[0], /name,business,email,phone,source,hook,score/, 'csv header');
  console.log('✓ CSV exported');

  // 5) De-duplication on a second identical run
  const second = await runLeadHunt('find 50 dentists in Austin with email and phone', { dataDir, dbPath, csvPath });
  assert.strictEqual(second.stats.inserted, 0, 'second run should insert 0 (all dupes)');
  assert.strictEqual(second.stats.skipped, 5, 'second run should skip 5 dupes');
  console.log('✓ de-duplication works across runs');

  fs.rmSync(dataDir, { recursive: true, force: true });
  console.log('\nAll smoke checks passed. ✅');
}

run().catch((err) => {
  console.error('\n❌ Smoke test failed:', err.message);
  process.exit(1);
});
