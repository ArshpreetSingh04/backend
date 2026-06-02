'use strict';

/**
 * Search-provider configs for the web-search discovery adapter. A provider just
 * tells the adapter where the search box is, how to submit, when results are
 * ready, and how to read a business name + website off a result page — so new
 * engines are config, not code.
 */

// Live, general web-search provider. Selectors are best-effort and NOT
// verifiable in this environment because open-web egress is blocked by the
// network allowlist ("Host not in allowlist"). [needs-key:network-egress]
const DUCKDUCKGO = {
  name: 'duckduckgo',
  homeUrl: 'https://duckduckgo.com/',
  searchBox: 'input[name="q"]',
  submit: 'enter',
  resultsReady: '[data-testid="result"], li.result, #links .result',
  resultLink: '[data-testid="result-title-a"], a.result__a',
  extract: { name: ['h1', 'title'], website: [] }, // website falls back to URL host
  note: 'Selectors best-effort; unverified here (open-web egress blocked).',
};

/**
 * Build a provider pointing at the local verification fixture.
 * @param {string} baseUrl e.g. http://127.0.0.1:54321
 */
function makeFixtureProvider(baseUrl) {
  const base = baseUrl.replace(/\/$/, '');
  return {
    name: 'fixture',
    homeUrl: `${base}/`,
    searchBox: 'input[name="q"]',
    submit: 'enter',
    resultsReady: '.result',
    resultLink: '.result a.result-link',
    extract: { name: ['h1.biz-name', 'h1', 'title'], website: ['a.biz-website'] },
  };
}

module.exports = { DUCKDUCKGO, makeFixtureProvider };
