'use strict';

/**
 * webSearchAdapter — ONE concrete, REAL discovery path.
 *
 * It drives a real browser (via HumanBrowser) to: open a search engine, type a
 * query built from the target profile (niche + location), submit, wait for the
 * organic results, then open the top results one by one and read off the real
 * business name + website/domain + the source URL.
 *
 * All page *interactions* are human-like (mouse/keyboard). Pulling text/attrs
 * off a result page for extraction is a read, which is allowed.
 */

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

function normalizeDomain(value) {
  if (!value) return '';
  const s = String(value).trim();
  if (/^https?:\/\//i.test(s)) return hostOf(s);
  return s.replace(/^www\./, '').replace(/\/.*$/, '').trim();
}

async function firstText(page, selectors) {
  for (const sel of selectors) {
    const loc = page.locator(sel).first();
    if (await loc.count()) {
      const t = (await loc.innerText().catch(() => '')).trim();
      if (t) return t;
    }
  }
  return '';
}

async function firstWebsite(page, selectors) {
  for (const sel of selectors) {
    const loc = page.locator(sel).first();
    if (await loc.count()) {
      const href = await loc.getAttribute('href').catch(() => null);
      if (href) return normalizeDomain(href);
      const t = (await loc.innerText().catch(() => '')).trim();
      if (t) return normalizeDomain(t);
    }
  }
  return '';
}

/**
 * @param {object} args
 * @param {import('../browser/humanBrowser').HumanBrowser} args.hb
 * @param {object} args.provider
 * @param {{vertical:string, location:string|null}} args.profile
 * @param {number} [args.maxResults]
 * @param {(m:string)=>void} [args.log]
 * @returns {Promise<Array<{business:string, website:string, source:string, rank:number}>>}
 */
async function discover({ hb, provider, profile, maxResults = 5, log = () => {}, progress = () => {} }) {
  const page = hb.page;
  // Prefer the engine's shaped query (niche + location + extra qualifiers);
  // fall back to the legacy niche+location for any older caller.
  const query = (profile.query
    || [profile.niche || profile.vertical, profile.location].filter(Boolean).join(' ')).trim();
  log(`web-search query: "${query}" via ${provider.name}`);

  // Open the search engine and type the query like a person.
  await hb.goto(provider.homeUrl);
  await page.waitForSelector(provider.searchBox, { timeout: 15000 });
  const box = page.locator(provider.searchBox).first();
  await hb.type(box, query);

  if (provider.submit === 'enter') {
    await hb.pressEnter();
  } else {
    await hb.click(page.locator(provider.submit).first());
  }

  await page.waitForSelector(provider.resultsReady, { timeout: 20000 });
  await hb.scroll(2);

  const total = await page.locator(provider.resultLink).count();
  const n = Math.min(total, maxResults);
  log(`organic results: ${total}; opening top ${n}`);

  const out = [];
  for (let i = 0; i < n; i++) {
    // Re-locate each iteration since we navigate away and back.
    const link = page.locator(provider.resultLink).nth(i);
    if (!(await link.count())) break;

    await hb.click(link); // real click → real navigation to the result page
    await page.waitForLoadState('domcontentloaded').catch(() => {});
    await hb.settle();

    const url = page.url();
    let business = await firstText(page, provider.extract?.name || ['h1', 'title']);
    if (!business) business = (await page.title().catch(() => '')).trim();

    let website = await firstWebsite(page, provider.extract?.website || []);
    if (!website) website = hostOf(url);

    business = business.replace(/\s+/g, ' ').trim();
    if (business && website) {
      out.push({ business, website, source: url, rank: i + 1 });
      log(`  #${i + 1} ${business} — ${website}`);
      progress('business-found', `Found ${business} (${website})`, { business, website, rank: i + 1 });
    }

    await hb.back();
    await page.waitForSelector(provider.resultsReady, { timeout: 15000 }).catch(() => {});
  }

  return out;
}

module.exports = { discover, normalizeDomain, hostOf };
