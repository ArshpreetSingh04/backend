'use strict';

/**
 * storage — local persistence for leads using Node's built-in SQLite
 * (node:sqlite, Node >= 22). No native compilation, no extra deps.
 */

const { DatabaseSync } = require('node:sqlite');
const path = require('node:path');
const fs = require('node:fs');

class LeadStore {
  /** @param {string} dbPath absolute path to the sqlite file */
  constructor(dbPath) {
    this.dbPath = dbPath;
    fs.mkdirSync(path.dirname(dbPath), { recursive: true });
    this.db = new DatabaseSync(dbPath);
    this.#migrate();
  }

  #migrate() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS hunts (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt    TEXT NOT NULL,
        plan_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE IF NOT EXISTS leads (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        hunt_id   INTEGER REFERENCES hunts(id),
        name      TEXT,
        business  TEXT,
        website   TEXT,
        email     TEXT,
        phone     TEXT,
        source    TEXT,
        hook      TEXT,
        score     INTEGER,
        dedupe_key TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      -- Prevent the same business/contact being stored twice.
      CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_dedupe ON leads(dedupe_key);
    `);

    // Guarded migration: add `website` to DBs created before WO#2.
    const cols = this.db.prepare('PRAGMA table_info(leads)').all().map((c) => c.name);
    if (!cols.includes('website')) {
      this.db.exec('ALTER TABLE leads ADD COLUMN website TEXT');
    }
  }

  /**
   * Record a hunt (the prompt + plan) and return its id.
   * @param {string} prompt
   * @param {object} plan
   * @returns {number} huntId
   */
  recordHunt(prompt, plan) {
    const stmt = this.db.prepare(
      'INSERT INTO hunts (prompt, plan_json) VALUES (?, ?)',
    );
    const info = stmt.run(prompt, JSON.stringify(plan ?? null));
    return Number(info.lastInsertRowid);
  }

  /**
   * Insert leads, skipping ones whose dedupe_key already exists.
   * @param {number} huntId
   * @param {Array<object>} leads
   * @returns {{inserted:number, skipped:number}}
   */
  insertLeads(huntId, leads) {
    const stmt = this.db.prepare(`
      INSERT OR IGNORE INTO leads
        (hunt_id, name, business, website, email, phone, source, hook, score, dedupe_key)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    let inserted = 0;
    let skipped = 0;
    for (const l of leads) {
      const key = dedupeKey(l);
      const info = stmt.run(
        huntId,
        l.name ?? null,
        l.business ?? null,
        l.website ?? null,
        l.email ?? null,
        l.phone ?? null,
        l.source ?? null,
        l.hook ?? null,
        l.score ?? null,
        key,
      );
      if (info.changes > 0) inserted += 1;
      else skipped += 1;
    }
    return { inserted, skipped };
  }

  /** All leads, newest first. @returns {Array<object>} */
  allLeads() {
    return this.db
      .prepare('SELECT * FROM leads ORDER BY id DESC')
      .all();
  }

  close() {
    this.db.close();
  }
}

/**
 * Stable key for de-duplication: prefer email, then phone, then name+business.
 * @param {object} lead
 */
function dedupeKey(lead) {
  const norm = (s) => String(s || '').toLowerCase().replace(/\s+/g, ' ').trim();
  if (lead.email) return `email:${norm(lead.email)}`;
  if (lead.phone) return `phone:${norm(lead.phone).replace(/[^\d+]/g, '')}`;
  if (lead.website) return `web:${norm(lead.website).replace(/^www\./, '')}`;
  return `nb:${norm(lead.name)}|${norm(lead.business)}`;
}

module.exports = { LeadStore, dedupeKey };
