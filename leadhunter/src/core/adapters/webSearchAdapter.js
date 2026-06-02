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

// --- ad / aggregator filtering ---------------------------------------------
// Real-mode discovery must yield actual individual business sites, not ad
// redirects or directory/aggregator pages. This is smarter *reading* of the
// real SERP (still human-like; never raw HTTP).

// Ad / tracking redirect links (DDG → /y.js, Bing → /aclick, Google → /aclk).
const AD_LINK_RE = /\/y\.js\b|\/aclick\b|\/aclk\b|[?&]ad_(domain|provider)=|googleadservices/i;

// Search engines themselves (ad links resolve back here) + well-known
// directories / aggregators / review sites / socials / listicle publishers that
// are not an individual business homepage.
const EXCLUDED_DOMAINS = new Set([
  'duckduckgo.com', 'bing.com', 'google.com',
  'yelp.com', 'zocdoc.com', 'opencare.com', 'yellowpages.com', 'healthgrades.com',
  'mapquest.com', 'tripadvisor.com', 'angi.com', 'angieslist.com', 'thumbtack.com',
  'bbb.org', 'nextdoor.com', 'glassdoor.com', 'indeed.com',
  'facebook.com', 'instagram.com', 'linkedin.com', 'twitter.com', 'x.com',
  'pinterest.com', 'youtube.com', 'reddit.com', 'wikipedia.org',
  'nytimes.com', 'forbes.com', 'usnews.com', 'statesman.com', 'yahoo.com',
]);

/** Reduce a host to its registrable-ish root (last two labels). */
function rootDomain(hostOrDomain) {
  const h = String(hostOrDomain || '').toLowerCase().replace(/^www\./, '').replace(/\/.*$/, '');
  const parts = h.split('.').filter(Boolean);
  return parts.length <= 2 ? h : parts.slice(-2).join('.');
}

function isAdLink(href) {
  return !!href && AD_LINK_RE.test(href);
}

function isExcludedDomain(hostOrDomain) {
  return EXCLUDED_DOMAINS.has(rootDomain(hostOrDomain));
}

// --- anti-bot / challenge-page detection -----------------------------------
// Recognise the screens search engines show automated browsers (e.g. DuckDuckGo
// redirects to /static-pages/418.html) so we emit a precise diagnostic instead
// of a silent selector timeout.
const BLOCK_URL_RE = /static-pages\/4\d\d|\/sorry\b|\/challenge|\/captcha|unusual[-_]?traffic/i;
const BLOCK_TEXT_MARKERS = [
  'unusual traffic',
  'our systems have detected',
  'are you a robot',
  'verify you are human',
  'verify you’re human',
  'automated queries',
  'detected unusual',
  'access denied',
  'please complete the captcha',
];

/** Inspect the current page for signs it's a block/challenge screen. */
async function detectBlock(page) {
  const url = page.url();
  if (BLOCK_URL_RE.test(url)) return { blocked: true, reason: `challenge/error URL (${url})`, url };
  let title = '';
  let text = '';
  try { title = (await page.title()) || ''; } catch { /* ignore */ }
  try { text = (await page.locator('body').innerText().catch(() => '')).slice(0, 2000); } catch { /* ignore */ }
  const hay = `${title}\n${text}`.toLowerCase();
  const marker = BLOCK_TEXT_MARKERS.find((m) => hay.includes(m));
  if (marker) return { blocked: true, reason: `block marker "${marker}"`, url };
  return { blocked: false, url };
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

  // Fail with a clear, specific reason instead of a silent selector timeout.
  const reportBlock = (b) => {
    const msg =
      `Search provider "${provider.name}" served an anti-bot block/challenge page — ${b.reason}. ` +
      `Real-browser discovery was screened, so no leads were found. ` +
      `Try a headed browser (LEADHUNTER_HEADFUL=1 under xvfb) or an alternate provider (LEADHUNTER_PROVIDER=bing).`;
    progress('blocked', msg, { provider: provider.name, url: b.url });
    log(`BLOCKED: ${b.reason}`);
    throw new Error(msg);
  };
  const waitForOrDiagnose = async (selector, timeout, label) => {
    try {
      await page.waitForSelector(selector, { timeout });
    } catch {
      const b = await detectBlock(page);
      if (b.blocked) reportBlock(b);
      const msg =
        `Timed out (${timeout}ms) waiting for ${label} on "${provider.name}" (selector: ${selector}). ` +
        `Current page: ${page.url()} — the real browser was likely screened, or the provider selectors are stale.`;
      progress('error', msg, { provider: provider.name, url: page.url() });
      log(msg);
      throw new Error(msg);
    }
  };

  // Open the search engine and type the query like a person.
  await hb.goto(provider.homeUrl);

  // Anti-bot screens often hit immediately (e.g. DDG redirects to static-pages/418).
  const preBlock = await detectBlock(page);
  if (preBlock.blocked) reportBlock(preBlock);

  await waitForOrDiagnose(provider.searchBox, 15000, 'the search box');
  const box = page.locator(provider.searchBox).first();
  await hb.type(box, query);

  if (provider.submit === 'enter') {
    await hb.pressEnter();
  } else {
    await hb.click(page.locator(provider.submit).first());
  }

  await waitForOrDiagnose(provider.resultsReady, 20000, 'organic results');
  await hb.scroll(2);

  const total = await page.locator(provider.resultLink).count();
  // Scan organic results, skipping ads + directories, until we have enough REAL
  // businesses (bounded so we never trawl the whole page).
  const maxScan = Math.min(total, maxResults * 4 + 10);
  log(`organic results: ${total}; selecting up to ${maxResults} real businesses`);

  const out = [];
  const skipped = { ads: 0, aggregators: 0, incomplete: 0 };
  for (let i = 0; i < total && out.length < maxResults && i < maxScan; i++) {
    // Re-locate each iteration since we navigate away and back.
    const link = page.locator(provider.resultLink).nth(i);
    if (!(await link.count())) break;

    // (a) Drop ad / tracking-redirect results without even opening them.
    const href = await link.getAttribute('href').catch(() => null);
    if (isAdLink(href)) {
      skipped.ads += 1;
      log(`  skip ad/redirect: ${(href || '').slice(0, 70)}`);
      continue;
    }

    await hb.click(link); // real click → real navigation to the result page
    await page.waitForLoadState('domcontentloaded').catch(() => {});
    await hb.settle();

    const url = page.url();
    let business = await firstText(page, provider.extract?.name || ['h1', 'title']);
    if (!business) business = (await page.title().catch(() => '')).trim();

    let website = await firstWebsite(page, provider.extract?.website || []);
    if (!website) website = hostOf(url);

    business = business.replace(/\s+/g, ' ').trim();

    // (b) Drop directory / aggregator / search-engine domains — not a business.
    if (isExcludedDomain(website) || isExcludedDomain(hostOf(url))) {
      skipped.aggregators += 1;
      log(`  skip aggregator/directory: ${website || hostOf(url)}`);
    } else if (business && website) {
      const rank = out.length + 1;
      out.push({ business, website, source: url, rank });
      log(`  #${rank} ${business} — ${website}`);
      progress('business-found', `Found ${business} (${website})`, { business, website, rank });
    } else {
      skipped.incomplete += 1;
      log(`  skip incomplete result: ${url}`);
    }

    await hb.back();
    await page.waitForSelector(provider.resultsReady, { timeout: 15000 }).catch(() => {});
  }

  log(`kept ${out.length} real businesses (skipped ${skipped.ads} ads, ${skipped.aggregators} aggregators, ${skipped.incomplete} incomplete)`);
  return out;
}

module.exports = {
  discover,
  normalizeDomain,
  hostOf,
  isAdLink,
  isExcludedDomain,
  rootDomain,
  EXCLUDED_DOMAINS,
};
