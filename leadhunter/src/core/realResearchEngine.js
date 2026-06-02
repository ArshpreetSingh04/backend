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

const { parsePrompt } = require('./promptParser');
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
    const parsed = parsePrompt(prompt);
    return {
      ...parsed,
      engine: this.name,
      provider: this.provider.name,
      sources: ['web_search', 'maps (stubbed) [needs-key:maps]'],
      steps: [
        `Open ${this.provider.name} and type "${parsed.vertical}${parsed.location ? ' ' + parsed.location : ''}"`,
        'Press Enter, wait for organic results, scroll human-like',
        `Open the top ${this.maxResults} results and read business name + website`,
        'Return leads; email/phone/hook left empty [needs-key:enrich]',
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

    return discoveries
      .filter((d) => d.business && d.website)
      .map((d) => ({
        name: null, // contact person unknown until enrichment [needs-key:enrich]
        business: d.business, // REAL business name from the result page
        website: d.website, // REAL website/domain
        email: null, // [needs-key:enrich]
        phone: null, // [needs-key:enrich]
        source: d.source, // REAL source URL where it was discovered
        hook: null, // [needs-key:enrich] / [needs-key:llm]
        score: Math.max(50, 100 - (d.rank - 1) * 8), // preliminary, rank-based
      }));
  }
}

module.exports = { RealResearchEngine };
