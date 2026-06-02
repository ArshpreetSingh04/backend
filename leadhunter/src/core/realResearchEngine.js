'use strict';

/**
 * RealResearchEngine — the real, browser-driven implementation of the same
 * ResearchEngine interface the mock uses ({ name, plan, findLeads }). It drives
 * a real Chromium via HumanBrowser and discovers real businesses from the open
 * web through the web-search adapter.
 *
 * Fields it cannot yet fill (contact name, email, phone, personalization hook)
 * are left null and flagged [needs-key:enrich] — never faked. Score is a
 * preliminary, honest signal derived from organic search rank.
 */

const { parseTargetProfile } = require('./promptParser');
const { HumanBrowser } = require('./browser/humanBrowser');
const webSearch = require('./adapters/webSearchAdapter');
const maps = require('./adapters/mapsAdapter');
const { DUCKDUCKGO } = require('./adapters/providers');

class RealResearchEngine {
  /**
   * @param {object} [opts]
   * @param {object} [opts.provider]   search-provider config (defaults to DuckDuckGo)
   * @param {boolean} [opts.headless]  default true
   * @param {number} [opts.maxResults] default 5
   * @param {(m:string)=>void} [opts.log]
   */
  constructor(opts = {}) {
    this.name = 'real';
    this.provider = opts.provider || DUCKDUCKGO;
    this.headless = opts.headless !== false;
    this.maxResults = opts.maxResults || 5;
    this.log = opts.log || ((m) => console.log(`[real] ${m}`));
  }

  async plan(prompt) {
    // WO#4: consume the rich TargetProfile (not the legacy parsePrompt view).
    const profile = parseTargetProfile(prompt);
    const query = buildQuery(profile);
    return {
      ...profile, // raw, niche, role, location, count, requiredContactFields, extraQualifiers
      query, // niche + location + extraQualifiers, ready to type into the search box
      engine: this.name,
      provider: this.provider.name,
      sources: ['web_search', 'maps (stubbed) [needs-key:maps]'],
      // Backward-compatible aliases for the adapter / older consumers.
      vertical: profile.niche,
      fields: profile.requiredContactFields,
      steps: [
        `Open ${this.provider.name} and type "${query}"`,
        'Press Enter, wait for organic results, scroll human-like',
        `Open the top ${this.maxResults} results and read business name + website`,
        `Qualify on required fields [${profile.requiredContactFields.join(', ')}]` +
          (profile.extraQualifiers.length ? `; score boosts for: ${profile.extraQualifiers.join(', ')}` : ''),
      ],
    };
  }

  async findLeads(prompt, opts = {}) {
    const plan = await this.plan(prompt);
    const limit = opts.limit || this.maxResults;

    const hb = new HumanBrowser({ headless: this.headless, log: this.log });
    let discoveries = [];
    try {
      await hb.launch();
      discoveries = await webSearch.discover({
        hb,
        provider: this.provider,
        profile: plan,
        maxResults: limit,
        log: this.log,
      });
    } finally {
      await hb.close();
    }

    // Maps discovery is stubbed pending a key; it returns nothing for now.
    const mapsLeads = await maps.discover(plan); // [needs-key:maps]
    discoveries = discoveries.concat(mapsLeads);

    // Qualify + score using the TargetProfile (requiredContactFields, extraQualifiers).
    return qualifyLeads(discoveries, plan);
  }
}

// ---------------------------------------------------------------------------
// Pure helpers (no browser) — exported so they can be unit-tested offline.
// ---------------------------------------------------------------------------

/** Shape the search query from the profile: niche + location + extra qualifiers. */
function buildQuery(profile) {
  return [profile.niche, profile.location, ...(profile.extraQualifiers || [])]
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// Contact fields the discovery step can actually confirm right now. Everything
// else (email/phone/linkedin/address) needs enrichment we don't have yet, so a
// missing such field down-ranks a lead rather than dropping it. [needs-key:enrich]
const VERIFIABLE_NOW = new Set(['website']);
const MISSING_FIELD_PENALTY = 12;
const QUALIFIER_BONUS = 6;

function leadHas(lead, field) {
  const v = lead[field];
  return v != null && String(v).trim() !== '';
}

/** True if any meaningful word of the qualifier appears in the lead's text. */
function qualifierMatches(lead, qualifier) {
  const hay = `${lead.business || ''} ${lead.website || ''}`.toLowerCase();
  const tokens = (qualifier.toLowerCase().match(/[a-z]{3,}/g) || []);
  return tokens.some((t) => hay.includes(t));
}

/**
 * Map raw discoveries to qualified, scored leads using the TargetProfile.
 * - A lead must have a business name + website to exist at all.
 * - Missing a *verifiable-now* required field (website) → dropped.
 * - Missing an enrichment-gated required field (email/phone/…) → down-ranked,
 *   never faked. [needs-key:enrich]
 * - Each matched extra qualifier nudges the score up.
 *
 * @param {Array<{business,website,source,rank}>} discoveries
 * @param {object} profile  TargetProfile (requiredContactFields, extraQualifiers)
 */
function qualifyLeads(discoveries, profile) {
  const required = profile.requiredContactFields || [];
  const extras = profile.extraQualifiers || [];
  const out = [];

  for (const d of discoveries) {
    if (!d.business || !d.website) continue; // every lead needs a name + site

    const lead = {
      name: null, // [needs-key:enrich]
      business: d.business,
      website: d.website,
      email: null, // [needs-key:enrich]
      phone: null, // [needs-key:enrich]
      source: d.source,
      hook: null, // [needs-key:enrich] / [needs-key:llm]
      score: 0,
    };

    let score = Math.max(50, 100 - (d.rank - 1) * 8); // preliminary rank-based base
    let drop = false;
    for (const f of required) {
      if (leadHas(lead, f)) continue;
      if (VERIFIABLE_NOW.has(f)) {
        drop = true; // genuinely missing a field we can confirm → disqualify
        break;
      }
      score -= MISSING_FIELD_PENALTY; // can't confirm yet → down-rank, keep
    }
    if (drop) continue;

    for (const q of extras) {
      if (qualifierMatches(lead, q)) score += QUALIFIER_BONUS;
    }

    lead.score = Math.max(1, Math.min(100, Math.round(score)));
    out.push(lead);
  }

  return out;
}

module.exports = { RealResearchEngine, buildQuery, qualifyLeads };
