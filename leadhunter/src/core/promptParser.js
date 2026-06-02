'use strict';

/**
 * promptParser — converts a natural-language "Find Leads" prompt into a
 * structured TargetProfile:
 *
 *   TargetProfile = {
 *     raw:                  string,        // the original prompt
 *     niche:                string,        // business type / role ("dentists", "saas marketing managers")
 *     role:                 string,        // alias of niche (the "niche/role" concept)
 *     location:             string|null,   // "Austin", "Denver", "NYC", "New York City"
 *     count:                number,        // requested quantity, or a sensible default
 *     requiredContactFields:string[],      // ["email","phone","website","linkedin", ...]
 *     extraQualifiers:      string[],      // leftover constraints ("50+ employees", "5 star reviews")
 *   }
 *
 * Parsing is DETERMINISTIC and rule-based — no LLM dependency. A clean seam is
 * provided to swap in a pluggable LLM parser later via `opts.parser` or
 * `setDefaultProfileParser()`. [needs-key:llm]
 *
 * Examples:
 *   "find 50 dentists in Austin with email and phone"
 *     -> niche "dentists", location "Austin", count 50, fields [email, phone]
 *   "get 20 plumbers near Denver with a website"
 *     -> niche "plumbers", location "Denver", count 20, fields [website]
 *   "100 SaaS marketing managers in NYC with LinkedIn"
 *     -> niche "saas marketing managers", location "NYC", count 100, fields [linkedin]
 *   "find roofing contractors in Miami"            (no count given)
 *     -> niche "roofing contractors", location "Miami", count DEFAULT, fields [email, phone]
 */

const DEFAULT_COUNT = 25;
const MAX_COUNT = 500;

// Prepositions that introduce a location ("in Austin", "near Denver").
const LOCATION_HINTS = ['in', 'near', 'around', 'within', 'across'];

// Clause keywords that introduce contact fields / qualifiers ("with email…",
// "that have…", "who have…"). Everything from here on is NOT part of the niche.
const QUALIFIER_HINTS = ['with', 'that', 'who', 'having', 'including', 'plus', 'whose'];

// Filler words stripped when isolating the niche/role.
const STOPWORDS = new Set([
  'find', 'get', 'fetch', 'pull', 'list', 'show', 'give', 'me', 'some', 'all',
  'a', 'an', 'the', 'leads', 'lead', 'for', 'of', 'please', 'any', 'top', 'best',
]);

// Canonical contact fields and the phrases that imply them. Order here defines
// the order of requiredContactFields.
const FIELD_SYNONYMS = {
  email: ['email', 'emails', 'e-mail', 'e-mails', 'mail'],
  phone: ['phone', 'phones', 'phone number', 'phone numbers', 'number', 'numbers', 'tel', 'telephone', 'mobile', 'cell'],
  website: ['website', 'websites', 'site', 'web', 'url', 'homepage'],
  linkedin: ['linkedin', 'linked in', 'linkedin profile', 'linkedin url'],
  address: ['address', 'addresses', 'street address', 'mailing address'],
};

// ---------------------------------------------------------------------------
// The deterministic, rule-based parser (the real WO#3 implementation).
// ---------------------------------------------------------------------------

/**
 * @param {string} prompt
 * @returns {TargetProfile}
 */
function ruleBasedTargetProfile(prompt) {
  const raw = String(prompt || '').trim();
  const lower = raw.toLowerCase();

  const count = extractCount(lower);
  const location = extractLocation(raw);
  const niche = extractNiche(lower);
  const { fields, extraQualifiers } = extractFieldsAndQualifiers(lower);
  const requiredContactFields = fields.length ? fields : ['email', 'phone'];

  return {
    raw,
    niche,
    role: niche, // the "niche/role" is a single concept; expose under both names
    location,
    count,
    requiredContactFields,
    extraQualifiers,
  };
}

function extractCount(lower) {
  // A number is the lead count only if it is NOT immediately followed by a
  // qualifier word (so "50+ employees" / "5 star reviews" / "10%" are skipped).
  const QUALIFIER_AFTER = /^(\+|%|k\b|m\b|star|stars|employee|employees|review|reviews|year|years|mile|miles|mi\b|km\b)/;
  const re = /\b(\d{1,5})\b\s*([a-z%+]*)/g;
  let m;
  while ((m = re.exec(lower)) !== null) {
    const n = parseInt(m[1], 10);
    const after = m[2] || '';
    if (QUALIFIER_AFTER.test(after)) continue;
    if (n > 0) return Math.min(n, MAX_COUNT);
  }
  return DEFAULT_COUNT;
}

function extractLocation(raw) {
  // "<hint> <Location>" up to a clause boundary (with/that/who/…), a delimiter,
  // or end of string. Preserves original casing ("NYC", "New York City").
  const hints = LOCATION_HINTS.join('|');
  const stops = QUALIFIER_HINTS.join('|');
  const re = new RegExp(
    `\\b(?:${hints})\\s+(.+?)(?:\\s+(?:${stops})\\b|[,.;]|$)`,
    'i',
  );
  const m = raw.match(re);
  if (!m) return null;
  const loc = m[1].trim();
  return loc || null;
}

function extractNiche(lower) {
  let s = ` ${lower} `;
  // Drop the location clause and everything after it.
  s = s.replace(new RegExp(`\\b(?:${LOCATION_HINTS.join('|')})\\b.*$`), ' ');
  // Drop the qualifier/contact clause and everything after it.
  s = s.replace(new RegExp(`\\b(?:${QUALIFIER_HINTS.join('|')})\\b.*$`), ' ');

  const tokens = s
    .replace(/[^a-z0-9\s-]/g, ' ')
    .split(/\s+/)
    .filter((t) => t && !STOPWORDS.has(t) && !/^\d+$/.test(t));

  return tokens.join(' ').trim() || 'businesses';
}

/** Detect canonical contact fields mentioned anywhere in the text. */
function detectFields(text) {
  const found = [];
  for (const [field, synonyms] of Object.entries(FIELD_SYNONYMS)) {
    const hit = synonyms.some((syn) => new RegExp(`\\b${escapeRe(syn)}\\b`).test(text));
    if (hit) found.push(field);
  }
  return found;
}

function extractFieldsAndQualifiers(lower) {
  const fields = detectFields(lower);

  // The qualifier clause = everything after the first qualifier hint.
  const clauseRe = new RegExp(`\\b(?:${QUALIFIER_HINTS.join('|')})\\b\\s*(.+)$`);
  const clause = lower.match(clauseRe);

  const extraQualifiers = [];
  if (clause) {
    const items = clause[1]
      .split(/\band\b|,|;|\bplus\b/)
      .map((s) => s.replace(/^(a|an|the|their|valid|verified|your|with|some)\s+/, '').trim())
      .filter(Boolean);

    for (const item of items) {
      // Skip items that are purely a contact field (already captured above).
      const isFieldOnly = detectFields(item).length > 0 && item.split(/\s+/).length <= 2;
      if (isFieldOnly) continue;
      extraQualifiers.push(item);
    }
  }

  return { fields, extraQualifiers };
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ---------------------------------------------------------------------------
// Injectable parser seam — deterministic by default, LLM-pluggable later.
// ---------------------------------------------------------------------------

/**
 * Parse a prompt into a TargetProfile.
 *
 * @param {string} prompt
 * @param {{parser?: (p:string)=>object}} [opts]  inject a custom parser (e.g. an
 *        LLM-backed one) for this call; otherwise the configured default is used.
 * @returns {TargetProfile|Promise<TargetProfile>}
 */
function parseTargetProfile(prompt, opts = {}) {
  // [needs-key:llm] Inject an LLM parser via opts.parser or setDefaultProfileParser().
  const parser = opts.parser || parseTargetProfile._default || ruleBasedTargetProfile;
  return parser(prompt);
}
parseTargetProfile._default = ruleBasedTargetProfile;

/** Swap the default parser (e.g. an LLM-backed one). Pass nothing to reset. */
function setDefaultProfileParser(fn) {
  parseTargetProfile._default = fn || ruleBasedTargetProfile;
}

// ---------------------------------------------------------------------------
// Backward-compatible legacy view used by the research engines, CLI and smoke
// test. Always deterministic. (vertical = niche, fields = requiredContactFields)
// ---------------------------------------------------------------------------

/**
 * @param {string} prompt
 * @returns {{count:number, vertical:string, location:string|null, fields:string[], raw:string}}
 */
function parsePrompt(prompt) {
  const p = ruleBasedTargetProfile(prompt);
  return {
    raw: p.raw,
    count: p.count,
    vertical: p.niche,
    location: p.location,
    fields: p.requiredContactFields,
  };
}

module.exports = {
  parseTargetProfile,
  ruleBasedTargetProfile,
  setDefaultProfileParser,
  parsePrompt,
  DEFAULT_COUNT,
  MAX_COUNT,
  FIELD_SYNONYMS,
};
