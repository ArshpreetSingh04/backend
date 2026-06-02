'use strict';

const { parsePrompt } = require('./promptParser');

/**
 * researchEngine — the heart of LeadHunter, behind a clean interface.
 *
 * The contract is deliberately small so the current MOCK implementation can be
 * swapped for the real one (which will drive a real browser in a human-like way
 * via Playwright/CDP — real mouse & keyboard, never raw JS injection) without
 * any change to the UI or the pipeline:
 *
 *   interface ResearchEngine {
 *     name: string
 *     plan(prompt: string): Promise<SearchPlan>
 *     findLeads(prompt: string, opts?): Promise<Lead[]>
 *   }
 *
 *   Lead = { name, business, email, phone, source, hook, score }
 *
 * [needs-key:browser]   Real browser automation (Playwright/CDP) + proxy/session.
 * [needs-key:maps]      Google Maps / Places style discovery of businesses.
 * [needs-key:enrich]    Email/phone enrichment + verification provider.
 * [needs-key:llm]       LLM-backed planner and per-lead "hook" generation.
 */

class MockResearchEngine {
  constructor(opts = {}) {
    this.name = 'mock';
    this.progress = opts.progress || (() => {});
  }

  /**
   * Build a structured search plan from the natural-language prompt.
   * @param {string} prompt
   * @returns {Promise<object>} SearchPlan
   */
  async plan(prompt) {
    const parsed = parsePrompt(prompt);
    return {
      ...parsed,
      // What the REAL engine would do: pick sources, then drive a browser.
      // [needs-key:browser] [needs-key:maps]
      sources: ['google_maps', 'business_directory', 'company_website'],
      steps: [
        `Open browser and search "${parsed.vertical}${parsed.location ? ' in ' + parsed.location : ''}"`,
        'Scroll results human-like and open the top listings',
        `Extract ${parsed.fields.join(', ')} from each listing/website`,
        'Qualify, de-duplicate and enrich the leads',
      ],
      engine: this.name,
    };
  }

  /**
   * Return leads for the prompt. Currently returns 5 MOCK leads regardless of
   * the requested count, clearly flagged as mock data.
   *
   * @param {string} prompt
   * @param {{limit?:number}} [opts]
   * @returns {Promise<Array<{name,business,email,phone,source,hook,score}>>}
   */
  async findLeads(prompt, opts = {}) {
    const plan = await this.plan(prompt);
    this.progress('searching', `Searching for "${plan.vertical}${plan.location ? ' in ' + plan.location : ''}" (mock)`);
    const all = buildMockLeads(plan);
    const limit = opts.limit || plan.count || all.length;
    const leads = all.slice(0, Math.min(limit, all.length));
    for (const l of leads) {
      this.progress('business-found', `Found ${l.business}`, { business: l.business, website: l.website });
    }
    this.progress('qualifying', `Qualifying ${leads.length} leads`, { count: leads.length });
    return leads;
  }
}

/** Five deterministic-but-realistic mock leads tailored to the plan. */
function buildMockLeads(plan) {
  const place = plan.location || 'Austin';
  const vert = singularize(plan.vertical) || 'business';
  const VertTitle = titleCase(vert);

  const seeds = [
    { name: 'Dr. Maria Alvarez', business: `${place} Smile ${VertTitle} Co.`, source: 'google_maps' },
    { name: 'James Okafor', business: `Downtown ${VertTitle} Group`, source: 'business_directory' },
    { name: 'Priya Nair', business: `Lakeside ${VertTitle} Partners`, source: 'company_website' },
    { name: 'Tom Becker', business: `${place} Family ${VertTitle}`, source: 'google_maps' },
    { name: 'Wei Chen', business: `Northside ${VertTitle} Studio`, source: 'business_directory' },
  ];

  return seeds.map((s, i) => {
    const slug = s.business.toLowerCase().replace(/[^a-z0-9]+/g, '');
    return {
      name: s.name,
      business: s.business,
      website: `${slug}.example.com`, // mock domain
      email: `contact@${slug}.example.com`, // [needs-key:enrich] mock, unverified
      phone: `+1-512-555-${String(1000 + i * 137).padStart(4, '0')}`,
      source: s.source,
      hook: `Recently ${['expanded hours', 'launched a new website', 'hiring staff', 'opened a 2nd location', 'running promos'][i]} — good moment to reach out about ${plan.vertical}.`,
      score: 92 - i * 7, // 92, 85, 78, 71, 64
    };
  });
}

function singularize(word) {
  if (!word) return word;
  const last = word.split(/\s+/).pop();
  if (/ies$/.test(last)) return word.replace(/ies$/, 'y');
  if (/(s|es)$/.test(last)) return word.replace(/(es|s)$/, '');
  return word;
}

function titleCase(s) {
  return String(s)
    .split(/\s+/)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ');
}

/**
 * Factory. Pass { mode: 'real' } in the future to get the browser-driven engine.
 * @param {{mode?:string}} [opts]
 */
function createEngine(opts = {}) {
  switch (opts.mode) {
    case 'real': {
      // Lazy require so the mock path never needs Playwright loaded.
      const { RealResearchEngine } = require('./realResearchEngine');
      return new RealResearchEngine(opts);
    }
    case 'mock':
    default:
      return new MockResearchEngine(opts);
  }
}

module.exports = { createEngine, MockResearchEngine };
