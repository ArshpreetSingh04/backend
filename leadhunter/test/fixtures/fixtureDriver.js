'use strict';

/**
 * fixtureDriver — a TEST-ONLY browser driver double.
 *
 * It implements the exact small surface the real adapters use from HumanBrowser
 * + Playwright's Page/Locator, but backed by the local search fixture's REAL
 * HTML parsed with node-html-parser (no Chromium). This lets the REAL engine
 * code (discover → ad/aggregator filter → qualify → enrich → dedupe) run
 * unchanged in restricted sandboxes where a Chromium binary cannot be
 * provisioned (the Playwright CDN is blocked by the egress allowlist).
 *
 * IMPORTANT: this is a test double. It is NEVER wired into production `--real`
 * runs — RealResearchEngine defaults to HumanBrowser+Chromium, and only the
 * verify scripts inject this driver, and only when no Chromium is available.
 * It is not a raw-HTTP discovery path: it only loads our own 127.0.0.1 fixture.
 *
 * Surface implemented (exactly what the adapters consume):
 *   driver: launch, goto, type, pressEnter, click, scroll, settle, back, close, .page
 *   page:   locator(sel), getByRole('link',{name}), url(), title(),
 *           waitForSelector(sel), waitForLoadState()
 *   locator: first(), nth(i), count(), innerText(), getAttribute(name)
 */

const http = require('node:http');
const fs = require('node:fs');
const { parse } = require('node-html-parser');
const { chromium } = require('playwright');

/** Is a real Chromium binary actually present (so the real path can run)? */
function chromiumAvailable() {
  const override = process.env.LEADHUNTER_CHROMIUM_PATH;
  if (override && fs.existsSync(override)) return true;
  try {
    const p = chromium.executablePath();
    return !!(p && fs.existsSync(p));
  } catch {
    return false;
  }
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (c) => { body += c; });
      res.on('end', () => resolve({ status: res.statusCode, location: res.headers.location, body }));
    });
    req.on('error', reject);
    req.setTimeout(5000, () => req.destroy(new Error('fixture request timeout')));
  });
}

const clean = (s) => String(s || '').replace(/\s+/g, ' ').trim();

/** Mirrors the slice of Playwright's Locator the adapters use. */
class FakeLocator {
  constructor(els) {
    this.els = els || [];
  }
  first() { return new FakeLocator(this.els.slice(0, 1)); }
  nth(i) { return new FakeLocator(this.els[i] ? [this.els[i]] : []); }
  async count() { return this.els.length; }
  async innerText() { return this.els[0] ? clean(this.els[0].text) : ''; }
  async getAttribute(name) {
    const v = this.els[0] ? this.els[0].getAttribute(name) : null;
    return v == null ? null : v;
  }
  _el() { return this.els[0] || null; }
}

class FixtureDriver {
  constructor(opts = {}) {
    this.log = opts.log || (() => {});
    this.stack = []; // [{ url, dom }] — navigation history snapshots
    this._formValues = {};
    this.page = this._makePage();
  }

  async launch() { this.log('launch: fixture driver (no Chromium)'); return this; }
  async close() {}

  get _cur() {
    return this.stack[this.stack.length - 1] || { url: '', dom: parse('<html></html>') };
  }

  _resolve(href) {
    try { return new URL(href, this._cur.url || 'http://127.0.0.1/').toString(); } catch { return href; }
  }

  async _fetchParse(url) {
    let cur = url;
    for (let hop = 0; hop < 5; hop++) {
      const r = await httpGet(cur);
      if (r.status >= 300 && r.status < 400 && r.location) {
        cur = new URL(r.location, cur).toString(); // follow redirect (e.g. block fixture)
        continue;
      }
      return { url: cur, dom: parse(r.body || '') };
    }
    return { url: cur, dom: parse('') };
  }

  // --- human-like surface (no real input; just navigates + reads HTML) ------
  async goto(url) {
    this.log(`navigate → ${url}`);
    this.stack.push(await this._fetchParse(url));
  }

  async type(locator, text) {
    const el = locator && locator._el && locator._el();
    const name = (el && el.getAttribute('name')) || 'q';
    this._formValues[name] = text;
  }

  async pressEnter() {
    const form = this._cur.dom.querySelector('form');
    const action = (form && form.getAttribute('action')) || '/';
    const qs = new URLSearchParams(this._formValues).toString();
    this._formValues = {};
    await this.goto(this._resolve(action + (qs ? `?${qs}` : '')));
  }

  async click(locator) {
    const el = locator && locator._el && locator._el();
    const href = el && el.getAttribute('href');
    if (href) await this.goto(this._resolve(href));
  }

  async scroll() {}
  async settle() {}
  async back() { if (this.stack.length > 1) this.stack.pop(); }

  // --- DOM reads ------------------------------------------------------------
  _query(selector) {
    const dom = this._cur.dom;
    const out = [];
    for (const part of String(selector).split(',')) {
      const s = part.trim();
      if (!s) continue;
      try {
        for (const el of dom.querySelectorAll(s)) if (!out.includes(el)) out.push(el);
      } catch { /* unsupported selector → no match */ }
    }
    return out;
  }

  _byRole(role, opts = {}) {
    if (role !== 'link') return [];
    const name = opts.name;
    const matches = name instanceof RegExp
      ? (t) => name.test(t)
      : (t) => !name || t.toLowerCase().includes(String(name).toLowerCase());
    return this._cur.dom.querySelectorAll('a').filter((a) => matches(clean(a.text)));
  }

  _makePage() {
    const self = this;
    return {
      locator: (sel) => new FakeLocator(self._query(sel)),
      getByRole: (role, opts) => new FakeLocator(self._byRole(role, opts)),
      url: () => self._cur.url,
      title: async () => {
        const t = self._cur.dom.querySelector('title');
        return t ? clean(t.text) : '';
      },
      waitForSelector: async (sel) => {
        if (self._query(sel).length) return true;
        throw new Error(`fixture waitForSelector timeout: ${sel}`);
      },
      waitForLoadState: async () => {},
    };
  }
}

module.exports = { FixtureDriver, FakeLocator, chromiumAvailable };
