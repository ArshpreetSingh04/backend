'use strict';

/**
 * promptParser — turns a natural-language "Find Leads" prompt into a structured
 * search plan. This is intentionally lightweight (regex/keyword based) for the
 * scaffold; the real version will likely hand the prompt to an LLM for planning.
 *
 * Example:
 *   "find 50 dentists in Austin with email and phone"
 *     -> { count: 50, vertical: "dentists", location: "Austin",
 *          fields: ["email", "phone"], raw: "..." }
 *
 * [needs-key:llm] A future LLM-backed planner would replace the heuristics here.
 */

const DEFAULT_COUNT = 25;
const MAX_COUNT = 500;

// Words that introduce a location ("in Austin", "near Boston", "around Denver").
const LOCATION_HINTS = ['in', 'near', 'around', 'within', 'across', 'from'];

// Filler words we strip when guessing the vertical (business type).
const STOPWORDS = new Set([
  'find', 'get', 'fetch', 'pull', 'list', 'show', 'me', 'some', 'all', 'a', 'an',
  'the', 'leads', 'lead', 'for', 'of', 'please', 'with', 'and', 'that', 'have',
  'having', 'who', 'which', 'including', 'plus', 'their',
]);

const FIELD_SYNONYMS = {
  email: ['email', 'emails', 'e-mail', 'mail'],
  phone: ['phone', 'phones', 'number', 'numbers', 'tel', 'telephone', 'mobile', 'cell'],
  website: ['website', 'site', 'url', 'web'],
  address: ['address', 'addresses', 'location', 'street'],
};

/**
 * @param {string} prompt
 * @returns {{count:number, vertical:string, location:string|null, fields:string[], raw:string}}
 */
function parsePrompt(prompt) {
  const raw = String(prompt || '').trim();
  const lower = raw.toLowerCase();

  const count = extractCount(lower);
  const fields = extractFields(lower);
  const location = extractLocation(raw);
  const vertical = extractVertical(raw, location);

  return { count, vertical, location, fields, raw };
}

function extractCount(lower) {
  const m = lower.match(/\b(\d{1,4})\b/);
  if (!m) return DEFAULT_COUNT;
  const n = parseInt(m[1], 10);
  if (!Number.isFinite(n) || n <= 0) return DEFAULT_COUNT;
  return Math.min(n, MAX_COUNT);
}

function extractFields(lower) {
  const found = new Set();
  for (const [field, synonyms] of Object.entries(FIELD_SYNONYMS)) {
    if (synonyms.some((s) => new RegExp(`\\b${s}\\b`).test(lower))) {
      found.add(field);
    }
  }
  // Default to the two fields people almost always want.
  if (found.size === 0) {
    found.add('email');
    found.add('phone');
  }
  return [...found];
}

function extractLocation(raw) {
  // Look for "<hint> <Location>" where Location is one or more Capitalized words,
  // optionally followed by a state/region (", TX" / "Texas").
  const pattern = new RegExp(
    `\\b(?:${LOCATION_HINTS.join('|')})\\s+([A-Z][\\w.-]+(?:\\s+[A-Z][\\w.-]+){0,2}(?:,\\s*[A-Z]{2})?)`,
  );
  const m = raw.match(pattern);
  return m ? m[1].trim() : null;
}

function extractVertical(raw, location) {
  let working = raw;

  // Drop everything from the location hint onward so the location words don't
  // bleed into the vertical guess.
  const locHintPattern = new RegExp(`\\b(?:${LOCATION_HINTS.join('|')})\\b.*$`, 'i');
  working = working.replace(locHintPattern, ' ');

  // Drop a trailing "with email and phone" style clause.
  working = working.replace(/\bwith\b.*$/i, ' ');

  const tokens = working
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, ' ')
    .split(/\s+/)
    .filter((t) => t && !STOPWORDS.has(t) && !/^\d+$/.test(t));

  const vertical = tokens.join(' ').trim();
  return vertical || 'businesses';
}

module.exports = { parsePrompt, DEFAULT_COUNT, MAX_COUNT };
