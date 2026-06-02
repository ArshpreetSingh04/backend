'use strict';

/**
 * HumanBrowser — a thin wrapper over Playwright/Chromium that does everything
 * the way a person would: real navigation, real mouse movement + clicks, real
 * keyboard typing, real scrolling, and randomized human-scale waits.
 *
 * HARD RULE for this project: interactions are performed ONLY through real
 * browser input (page.mouse / page.keyboard / page.goto). We never use
 * page.evaluate, injected scripts, or synthetic DOM events to *act* on a page.
 * Reading the DOM for extraction (locator.innerText / getAttribute / page.url)
 * is fine — those are reads, not actions.
 */

const { chromium } = require('playwright');

const USER_AGENT =
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

const rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

class HumanBrowser {
  /** @param {{headless?:boolean, log?:(m:string)=>void}} [opts] */
  constructor(opts = {}) {
    this.headless = opts.headless !== false;
    this.log = opts.log || (() => {});
    this.browser = null;
    this.context = null;
    this.page = null;
  }

  async launch() {
    this.browser = await chromium.launch({
      headless: this.headless,
      // --no-sandbox is needed in many CI/containers (Chromium setuid sandbox).
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    this.context = await this.browser.newContext({
      userAgent: USER_AGENT,
      viewport: { width: 1280, height: 800 },
      locale: 'en-US',
    });
    this.page = await this.context.newPage();
    return this.page;
  }

  /** Real navigation. */
  async goto(url) {
    this.log(`navigate → ${url}`);
    await this.page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await this.settle();
  }

  /** A human-scale pause. */
  async settle(min = 300, max = 800) {
    await this.page.waitForTimeout(rand(min, max));
  }

  /** Move the real mouse to the centre of an element (with a little jitter). */
  async #moveTo(locator) {
    const box = await locator.boundingBox();
    if (!box) return null;
    const x = box.x + box.width / 2 + rand(-4, 4);
    const y = box.y + box.height / 2 + rand(-3, 3);
    await this.page.mouse.move(x, y, { steps: rand(8, 20) });
    return { x, y };
  }

  /** Real mouse click: scroll into view, move the pointer, then press. */
  async click(locator) {
    await locator.scrollIntoViewIfNeeded().catch(() => {});
    const pos = await this.#moveTo(locator);
    await this.page.waitForTimeout(rand(80, 220));
    if (pos) {
      await this.page.mouse.click(pos.x, pos.y);
    } else {
      // Fallback still uses Playwright's real (trusted) input, not JS events.
      await locator.click();
    }
    await this.page.waitForTimeout(rand(150, 400));
  }

  /** Real keyboard typing, character by character with human-ish delays. */
  async type(locator, text) {
    await this.click(locator); // focus via a real click first
    await this.page.keyboard.type(text, { delay: rand(45, 130) });
  }

  async pressEnter() {
    await this.page.waitForTimeout(rand(120, 300));
    await this.page.keyboard.press('Enter');
  }

  /** Real wheel scrolling. */
  async scroll(times = 3) {
    for (let i = 0; i < times; i++) {
      await this.page.mouse.wheel(0, rand(250, 520));
      await this.page.waitForTimeout(rand(200, 500));
    }
  }

  async back() {
    await this.page.goBack({ waitUntil: 'domcontentloaded' }).catch(() => {});
    await this.settle();
  }

  async close() {
    if (this.browser) await this.browser.close();
  }
}

module.exports = { HumanBrowser, rand, USER_AGENT };
