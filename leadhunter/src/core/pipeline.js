'use strict';

/**
 * pipeline — orchestrates one "Find Leads" run end to end:
 *
 *   prompt
 *     -> engine.plan()        (parse the natural-language request)
 *     -> engine.findLeads()   (research; currently MOCK)
 *     -> dedupe               (in-memory, before persistence)
 *     -> persist to SQLite
 *     -> export to CSV
 *
 * This is the single seam the UI and CLI both call, so behaviour stays identical
 * whether a run is triggered from the desktop app or a script.
 */

const path = require('node:path');
const os = require('node:os');

const { createEngine } = require('./researchEngine');
const { LeadStore, dedupeKey } = require('./storage');
const { writeCsv } = require('./csv');

/** Default place to keep the user's data. */
function defaultDataDir() {
  return path.join(os.homedir(), '.leadhunter');
}

/**
 * @param {string} prompt
 * @param {object} [opts]
 * @param {string} [opts.dataDir]   where db + csv live
 * @param {string} [opts.dbPath]
 * @param {string} [opts.csvPath]
 * @param {string} [opts.mode]      engine mode ('mock' | 'real')
 * @returns {Promise<{prompt, plan, leads, stats, dbPath, csvPath, engine}>}
 */
async function runLeadHunt(prompt, opts = {}) {
  if (!prompt || !String(prompt).trim()) {
    throw new Error('Prompt is empty — type what leads you want, e.g. "find 50 dentists in Austin with email and phone".');
  }

  const dataDir = opts.dataDir || defaultDataDir();
  const dbPath = opts.dbPath || path.join(dataDir, 'leadhunter.db');
  const csvPath = opts.csvPath || path.join(dataDir, 'leads.csv');

  const engine = createEngine({ mode: opts.mode || 'mock' });

  const plan = await engine.plan(prompt);
  const rawLeads = await engine.findLeads(prompt, { limit: plan.count });
  const leads = dedupeInMemory(rawLeads);

  const store = new LeadStore(dbPath);
  let stats;
  try {
    const huntId = store.recordHunt(prompt, plan);
    stats = store.insertLeads(huntId, leads);
    // Export every lead we've ever stored so the CSV is a running master sheet.
    writeCsv(csvPath, store.allLeads());
  } finally {
    store.close();
  }

  return {
    prompt,
    plan,
    leads,
    stats: { found: rawLeads.length, ...stats },
    dbPath,
    csvPath,
    engine: engine.name,
  };
}

/** Remove duplicates within a single batch (DB also enforces uniqueness). */
function dedupeInMemory(leads) {
  const seen = new Set();
  const out = [];
  for (const l of leads) {
    const key = dedupeKey(l);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(l);
  }
  return out;
}

module.exports = { runLeadHunt, defaultDataDir };
