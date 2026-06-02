'use strict';

/**
 * searchFixture — a tiny REAL website (Node http, no deps) that behaves like a
 * search engine, so the RealResearchEngine can be verified end-to-end in a
 * locked-down environment where open-web egress is blocked.
 *
 * Routes:
 *   GET /                  search homepage with a real <form>/<input name="q">
 *   GET /search?q=...      organic results filtered from the dataset by the query
 *   GET /biz/:id           a business "website" page (name, domain, Contact link)
 *   GET /contact/:id       the business's contact page (mailto/tel for enrichment)
 *
 * The browser really navigates, types, clicks and scrolls against this; the
 * extracted names/domains are read from really-served HTML — not fabricated.
 *
 * `startFixture({ withJunk: true })` mixes in an ad-redirect result + a few
 * directory/aggregator results (Yelp/Zocdoc/Opencare) above the real businesses,
 * mirroring a live SERP, so ad/aggregator filtering can be verified offline.
 */

const http = require('node:http');

// A small, realistic dataset. Austin dentists (the happy path) plus a couple of
// non-matches to prove the query actually filters.
// `email`/`phone` are NOT shown on the result/biz page — they live on each
// business's contact page, so enrichment has to navigate there to find them.
// b2 deliberately has an email but NO phone, to prove partial/honest enrichment.
const BUSINESSES = [
  { id: 'b1', name: 'Austin Smiles Family Dental', domain: 'austinsmiles.example.com', niche: 'dentist dental', city: 'Austin', email: 'hello@austinsmiles.example.com', phone: '+1-512-555-0101' },
  { id: 'b2', name: 'Lone Star Dental Studio', domain: 'lonestardental.example.com', niche: 'dentist dental', city: 'Austin', email: 'frontdesk@lonestardental.example.com' },
  { id: 'b3', name: 'Congress Avenue Dentistry', domain: 'congressdentistry.example.com', niche: 'dentist dental dentistry', city: 'Austin', email: 'info@congressdentistry.example.com', phone: '+1-512-555-0103' },
  { id: 'b4', name: 'Barton Creek Dental Care', domain: 'bartoncreekdental.example.com', niche: 'dentist dental', city: 'Austin', email: 'care@bartoncreekdental.example.com', phone: '+1-512-555-0104' },
  { id: 'b5', name: 'Hill Country Family Dentists', domain: 'hillcountrydentists.example.com', niche: 'dentist dental', city: 'Austin', email: 'hello@hillcountrydentists.example.com', phone: '+1-512-555-0105' },
  { id: 'b6', name: 'Zilker Orthodontics & Dental', domain: 'zilkerortho.example.com', niche: 'dentist dental orthodontist', city: 'Austin', email: 'smile@zilkerortho.example.com', phone: '+1-512-555-0106' },
  { id: 'p1', name: 'Capital City Plumbing', domain: 'capitalcityplumbing.example.com', niche: 'plumber plumbing', city: 'Austin', email: 'dispatch@capitalcityplumbing.example.com', phone: '+1-512-555-0107' },
  { id: 'd1', name: 'Dallas Dental Group', domain: 'dallasdental.example.com', niche: 'dentist dental', city: 'Dallas', email: 'contact@dallasdental.example.com', phone: '+1-214-555-0108' },
];

// Junk results a live SERP mixes in above the real businesses: a sponsored ad
// (DDG-style /y.js redirect) and directory/aggregator pages. Verbatim-ish from a
// real "dentists in Austin" run. These must be filtered OUT by discovery.
const JUNK = [
  {
    id: 'ad1',
    kind: 'ad',
    name: 'Saints Dental Austin — Book Today',
    adHref: 'https://duckduckgo.com/y.js?ad_domain=saintsdental.example.com&ad_provider=bingv7aa&u3=https%3A%2F%2Fsaintsdental.example.com',
    niche: 'dentist dental', city: 'Austin',
  },
  { id: 'agg1', kind: 'aggregator', name: 'THE BEST 10 DENTISTS IN AUSTIN, TX - Yelp', domain: 'yelp.com', niche: 'dentist dental', city: 'Austin' },
  { id: 'agg2', kind: 'aggregator', name: 'Best Dentists Near Me in Austin, TX | Zocdoc', domain: 'zocdoc.com', niche: 'dentist dental', city: 'Austin' },
  { id: 'agg3', kind: 'aggregator', name: '20 Best Dentists Near Me | Opencare.com', domain: 'opencare.com', niche: 'dentist dental', city: 'Austin' },
];

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function stem(t) {
  return t.replace(/(ies)$/, 'y').replace(/s$/, '');
}

/** Rank a given dataset against the query (stable; preserves dataset order on ties). */
function rank(dataset, query) {
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean).map(stem);
  return dataset
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

function resultsPage(dataset, q) {
  const hits = rank(dataset, q);
  const items = hits
    .map((b) => {
      // Ad results link through a tracking redirect (no /biz page); organic
      // results link to the business "site".
      const href = b.kind === 'ad' ? b.adHref : `/biz/${b.id}`;
      const shown = b.kind === 'ad' ? 'Ad · sponsored' : (b.domain || '');
      return `<div class="result">
        <a class="result-link" href="${esc(href)}">${esc(b.name)}</a>
        <span class="result-url">${esc(shown)}</span>
      </div>`;
    })
    .join('\n');
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(q)} — FixtureSearch</title></head>
  <body><h1>Results for "${esc(q)}"</h1>
  ${items || '<p class="no-results">No results.</p>'}
  </body></html>`;
}

function bizPage(dataset, id) {
  const b = dataset.find((x) => x.id === id);
  if (!b) return null;
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(b.name)}</title></head>
  <body>
    <h1 class="biz-name">${esc(b.name)}</h1>
    <p>${esc(b.city)} — ${esc(b.niche)}</p>
    <a class="biz-website" href="https://${esc(b.domain)}">${esc(b.domain)}</a>
    <a class="contact-link" href="/contact/${esc(b.id)}">Contact us</a>
  </body></html>`;
}

// An anti-bot block/challenge screen, mimicking what DuckDuckGo serves to
// automated browsers (it redirects to /static-pages/418.html).
function blockPage() {
  return `<!doctype html><html><head><meta charset="utf-8"><title>DuckDuckGo</title></head>
  <body>
    <h1>If this error persists, please let us know.</h1>
    <p>Our systems have detected unusual traffic from your computer network. Please try again later.</p>
  </body></html>`;
}

function contactPage(dataset, id) {
  const b = dataset.find((x) => x.id === id);
  if (!b) return null;
  const email = b.email ? `<p>Email: <a class="email" href="mailto:${esc(b.email)}">${esc(b.email)}</a></p>` : '';
  const phone = b.phone ? `<p>Call: <a class="phone" href="tel:${esc(b.phone)}">${esc(b.phone)}</a></p>` : '';
  return `<!doctype html><html><head><meta charset="utf-8"><title>Contact — ${esc(b.name)}</title></head>
  <body>
    <h1>Contact ${esc(b.name)}</h1>
    ${email}
    ${phone}
  </body></html>`;
}

/**
 * Start the fixture on an ephemeral port.
 * @param {{block?:boolean, withJunk?:boolean}} [opts]
 *   block:true serves an anti-bot screen (homepage 302 → /static-pages/418.html).
 *   withJunk:true mixes ad + aggregator results above the real businesses.
 * @returns {Promise<{url:string, port:number, headers:object, dataset:object[], close:()=>Promise<void>}>}
 *        `headers` captures the User-Agent / Accept-Language of the last request.
 */
function startFixture(opts = {}) {
  const blockMode = !!opts.block;
  // Junk first, so it ranks at the top of the SERP (as on a real engine).
  const dataset = opts.withJunk ? [...JUNK, ...BUSINESSES] : BUSINESSES;
  const headers = { userAgent: null, acceptLanguage: null, count: 0 };

  const server = http.createServer((req, res) => {
    headers.userAgent = req.headers['user-agent'] || null;
    headers.acceptLanguage = req.headers['accept-language'] || null;
    headers.count += 1;
    const u = new URL(req.url, 'http://127.0.0.1');
    res.setHeader('Content-Type', 'text/html; charset=utf-8');

    if (blockMode) {
      if (u.pathname === '/') {
        res.statusCode = 302;
        res.setHeader('Location', '/static-pages/418.html');
        return res.end();
      }
      if (u.pathname.startsWith('/static-pages/')) return res.end(blockPage());
    }

    if (u.pathname === '/') return res.end(homePage());
    if (u.pathname === '/search') return res.end(resultsPage(dataset, u.searchParams.get('q') || ''));
    if (u.pathname.startsWith('/biz/')) {
      const body = bizPage(dataset, u.pathname.slice('/biz/'.length));
      if (body) return res.end(body);
      res.statusCode = 404;
      return res.end('<h1>404</h1>');
    }
    if (u.pathname.startsWith('/contact/')) {
      const body = contactPage(dataset, u.pathname.slice('/contact/'.length));
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
        headers, // captured User-Agent / Accept-Language of the last request
        dataset, // the ranked-able dataset this instance serves
        close: () => new Promise((r) => server.close(r)),
      });
    });
  });
}

module.exports = { startFixture, BUSINESSES, JUNK, rank };
