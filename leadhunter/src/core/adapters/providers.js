'use strict';

/**
 * Search-provider configs for the web-search discovery adapter.
 *
 * WO#10 (grounded in a live run): we navigate the real browser DIRECTLY to each
 * provider's results URL instead of the homepage → type → press-Enter dance.
 * That dance trips DuckDuckGo's bot screen (redirect to /static-pages/418) and
 * silently fails on Bing (Enter never submits — the page stays on the
 * autocomplete dropdown). Going straight to the results URL is still a REAL,
 * human-like browser navigation — we just drop the interaction that gets us
 * screened/stuck. (No raw HTTP: HumanBrowser.goto is a real navigation.)
 *
 * A provider exposes `searchUrl(query)` (the direct results page), the selector
 * that means results are ready, and how to read a result link. Business
 * name/website come from the LANDED page after a real click-through.
 */

// PRIMARY live provider — its direct results URL returns real organic .b_algo
// results headless, fast, with no block. Result links are /ck/a? redirect
// wrappers, so the true business domain is resolved from the landed page.url()
// after the click-through (and the denylist runs on that resolved host).
// cc/setlang nudge results toward the user's locale (the sandbox IP can be
// anywhere); the location term in the query also drives geo.
const BING = {
  name: 'bing',
  searchUrl: (q) => `https://www.bing.com/search?q=${encodeURIComponent(q)}&cc=US&setlang=en-US`,
  resultsReady: '#b_results .b_algo, li.b_algo',
  resultLink: '#b_results .b_algo h2 a, li.b_algo h2 a',
  extract: { name: ['h1', 'title'], website: [] }, // website ← resolved landed host
  note: 'Primary. Direct results URL returns organic results headless; type→Enter does not submit.',
};

// Kept as a FALLBACK. Screens headless (homepage→type→Enter and the direct
// results URL both redirect to static-pages/418), but may work headed or from a
// residential IP elsewhere — so it stays in the chain after Bing.
const DUCKDUCKGO = {
  name: 'duckduckgo',
  searchUrl: (q) => `https://duckduckgo.com/?q=${encodeURIComponent(q)}`,
  resultsReady: '[data-testid="result"], li.result, .result',
  resultLink: '[data-testid="result-title-a"], a.result__a',
  extract: { name: ['h1', 'title'], website: [] },
  note: 'Fallback. Tends to serve static-pages/418 to headless browsers.',
};

// Production live chain: Bing primary, DuckDuckGo fallback.
const LIVE_CHAIN = [BING, DUCKDUCKGO];

const PROVIDERS = { bing: BING, duckduckgo: DUCKDUCKGO };

/** Resolve a single provider config by name (case-insensitive); undefined if unknown. */
function getProvider(name) {
  return name ? PROVIDERS[String(name).trim().toLowerCase()] : undefined;
}

/**
 * Build a provider pointing at the local verification fixture.
 * @param {string} baseUrl e.g. http://127.0.0.1:54321
 */
function makeFixtureProvider(baseUrl) {
  const base = baseUrl.replace(/\/$/, '');
  return {
    name: 'fixture',
    searchUrl: (q) => `${base}/search?q=${encodeURIComponent(q)}`,
    resultsReady: '.result',
    resultLink: '.result a.result-link',
    extract: { name: ['h1.biz-name', 'h1', 'title'], website: ['a.biz-website'] },
  };
}

module.exports = { BING, DUCKDUCKGO, LIVE_CHAIN, PROVIDERS, getProvider, makeFixtureProvider };
