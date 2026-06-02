'use strict';

/**
 * searchFixture — a tiny REAL website (Node http, no deps) that behaves like a
 * search engine, so the RealResearchEngine can be verified end-to-end in a
 * locked-down environment where open-web egress is blocked.
 *
 * Routes:
 *   GET /                  search homepage with a real <form>/<input name="q">
 *   GET /search?q=...      organic results filtered from the dataset by the query
 *   GET /biz/:id           a business "website" page with name + displayed domain
 *
 * The browser really navigates, types, clicks and scrolls against this; the
 * extracted names/domains are read from really-served HTML — not fabricated.
 */

const http = require('node:http');

// A small, realistic dataset. Austin dentists (the happy path) plus a couple of
// non-matches to prove the query actually filters.
const BUSINESSES = [
  { id: 'b1', name: 'Austin Smiles Family Dental', domain: 'austinsmiles.example.com', niche: 'dentist dental', city: 'Austin' },
  { id: 'b2', name: 'Lone Star Dental Studio', domain: 'lonestardental.example.com', niche: 'dentist dental', city: 'Austin' },
  { id: 'b3', name: 'Congress Avenue Dentistry', domain: 'congressdentistry.example.com', niche: 'dentist dental dentistry', city: 'Austin' },
  { id: 'b4', name: 'Barton Creek Dental Care', domain: 'bartoncreekdental.example.com', niche: 'dentist dental', city: 'Austin' },
  { id: 'b5', name: 'Hill Country Family Dentists', domain: 'hillcountrydentists.example.com', niche: 'dentist dental', city: 'Austin' },
  { id: 'b6', name: 'Zilker Orthodontics & Dental', domain: 'zilkerortho.example.com', niche: 'dentist dental orthodontist', city: 'Austin' },
  { id: 'p1', name: 'Capital City Plumbing', domain: 'capitalcityplumbing.example.com', niche: 'plumber plumbing', city: 'Austin' },
  { id: 'd1', name: 'Dallas Dental Group', domain: 'dallasdental.example.com', niche: 'dentist dental', city: 'Dallas' },
];

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function stem(t) {
  return t.replace(/(ies)$/, 'y').replace(/s$/, '');
}

function rank(query) {
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean).map(stem);
  return BUSINESSES
    .map((b) => {
      const hay = `${b.name} ${b.niche} ${b.city}`.toLowerCase();
      const score = tokens.reduce((acc, t) => acc + (t && hay.includes(t) ? 1 : 0), 0);
      return { b, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((x) => x.b);
}

function homePage() {
  return `<!doctype html><html><head><meta charset="utf-8"><title>FixtureSearch</title></head>
  <body><h1>FixtureSearch</h1>
  <form action="/search" method="GET">
    <input name="q" type="text" placeholder="Search the web" autocomplete="off" style="width:480px">
    <button type="submit">Search</button>
  </form></body></html>`;
}

function resultsPage(q) {
  const hits = rank(q);
  const items = hits
    .map(
      (b) => `<div class="result">
        <a class="result-link" href="/biz/${b.id}">${esc(b.name)}</a>
        <span class="result-url">${esc(b.domain)}</span>
      </div>`,
    )
    .join('\n');
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(q)} — FixtureSearch</title></head>
  <body><h1>Results for "${esc(q)}"</h1>
  ${items || '<p class="no-results">No results.</p>'}
  </body></html>`;
}

function bizPage(id) {
  const b = BUSINESSES.find((x) => x.id === id);
  if (!b) return null;
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(b.name)}</title></head>
  <body>
    <h1 class="biz-name">${esc(b.name)}</h1>
    <p>${esc(b.city)} — ${esc(b.niche)}</p>
    <a class="biz-website" href="https://${esc(b.domain)}">${esc(b.domain)}</a>
  </body></html>`;
}

/**
 * Start the fixture on an ephemeral port.
 * @returns {Promise<{url:string, port:number, close:()=>Promise<void>}>}
 */
function startFixture() {
  const server = http.createServer((req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1');
    res.setHeader('Content-Type', 'text/html; charset=utf-8');

    if (u.pathname === '/') return res.end(homePage());
    if (u.pathname === '/search') return res.end(resultsPage(u.searchParams.get('q') || ''));
    if (u.pathname.startsWith('/biz/')) {
      const body = bizPage(u.pathname.slice('/biz/'.length));
      if (body) return res.end(body);
      res.statusCode = 404;
      return res.end('<h1>404</h1>');
    }
    res.statusCode = 404;
    res.end('<h1>404</h1>');
  });

  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolve({
        url: `http://127.0.0.1:${port}`,
        port,
        close: () => new Promise((r) => server.close(r)),
      });
    });
  });
}

module.exports = { startFixture, BUSINESSES };
