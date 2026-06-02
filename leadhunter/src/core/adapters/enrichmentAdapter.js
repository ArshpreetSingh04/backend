'use strict';

/**
 * enrichmentAdapter — REAL, human-like contact enrichment.
 *
 * After discovery+qualification, some leads are missing a required contact field
 * (email/phone). This adapter visits the lead's own site (its source page),
 * follows a "Contact"/"About" link like a person would (real navigation + mouse
 * click via the HumanBrowser seam — never raw JS or synthetic events), and reads
 * the email/phone off the page (DOM reads are allowed for extraction).
 *
 * It NEVER fabricates a value: a field is filled only if actually found.
 *
 * [needs-key:enrich] Third-party email/phone *verification* (deliverability/MX)
 * needs an API key; that step is stubbed (`verifyEmail`) and does not assert
 * validity until a key is provided.
 */

// Fields this adapter can obtain by visiting a site. (website is found during
// discovery; linkedin/address would need their own sources.)
const ENRICHABLE = new Set(['email', 'phone']);

function leadHas(lead, field) {
  const v = lead[field];
  return v != null && String(v).trim() !== '';
}

function isEmail(s) {
  return /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(s);
}

/** Find a human-clickable Contact/About link, if present. */
async function findContactLink(page) {
  const link = page.getByRole('link', { name: /contact|about/i }).first();
  if (await link.count()) return link;
  return null;
}

/** Read an email from the page: prefer a mailto: link, else scan visible text. */
async function extractEmail(page) {
  const mail = page.locator('a[href^="mailto:"]').first();
  if (await mail.count()) {
    const href = await mail.getAttribute('href').catch(() => null);
    if (href) {
      const e = href.replace(/^mailto:/i, '').split('?')[0].trim();
      if (isEmail(e)) return e;
    }
  }
  const text = await page.locator('body').innerText().catch(() => '');
  const m = text.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/);
  return m ? m[0] : null;
}

/** Read a phone from the page: prefer a tel: link, else scan visible text. */
async function extractPhone(page) {
  const tel = page.locator('a[href^="tel:"]').first();
  if (await tel.count()) {
    const href = await tel.getAttribute('href').catch(() => null);
    if (href) {
      const p = href.replace(/^tel:/i, '').trim();
      if (p) return p;
    }
  }
  const text = await page.locator('body').innerText().catch(() => '');
  const m = text.match(/\+?\d[\d\s().-]{7,}\d/);
  return m ? m[0].trim() : null;
}

/**
 * [needs-key:enrich] Verify an email via a 3rd-party API. Stubbed: we do not
 * claim validity without a key, and we never drop/alter the extracted value.
 */
function verifyEmail(_email) {
  return { verified: null, reason: 'needs-key:enrich' };
}

/** Visit one lead's site and try to fill its missing fields. */
async function enrichOne({ hb, lead, missing, log }) {
  const page = hb.page;
  const start = lead.source || (lead.website ? `https://${lead.website}` : null);
  if (!start) return {};

  try {
    await hb.goto(start); // real navigation back to the business's own page
    const contact = await findContactLink(page);
    if (contact) {
      await hb.click(contact); // real mouse click → real navigation
      await page.waitForLoadState('domcontentloaded').catch(() => {});
      await hb.settle();
    }
  } catch (err) {
    log(`enrich: could not open ${lead.business}: ${err.message}`);
    return {};
  }

  const found = {};
  if (missing.includes('email')) {
    const e = await extractEmail(page);
    if (e) {
      found.email = e;
      verifyEmail(e); // [needs-key:enrich] verification stub (no-op for now)
    }
  }
  if (missing.includes('phone')) {
    const p = await extractPhone(page);
    if (p) found.phone = p;
  }
  if (Object.keys(found).length) {
    log(`enriched "${lead.business}" → ${Object.keys(found).join(', ')}`);
  }
  return found;
}

/**
 * Enrich a batch of leads in place (only those missing a required, enrichable
 * field). Returns the same array.
 *
 * @param {object} args
 * @param {import('../browser/humanBrowser').HumanBrowser} args.hb  launched browser
 * @param {Array<object>} args.leads
 * @param {object} args.profile  TargetProfile (requiredContactFields)
 * @param {(m:string)=>void} [args.log]
 */
async function enrichLeads({ hb, leads, profile, log = () => {} }) {
  const wanted = (profile.requiredContactFields || []).filter((f) => ENRICHABLE.has(f));
  if (!wanted.length) return leads;

  for (const lead of leads) {
    const missing = wanted.filter((f) => !leadHas(lead, f));
    if (!missing.length) continue;
    const found = await enrichOne({ hb, lead, missing, log });
    Object.assign(lead, found);
  }
  return leads;
}

module.exports = { enrichLeads, verifyEmail, ENRICHABLE };
