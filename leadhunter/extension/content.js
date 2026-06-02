'use strict';

/**
 * LeadHunter Companion — content script. STUB.
 *
 * Eventual role: lightweight, read-only extraction of obvious business contact
 * details (name, phone, email, address) from the current page to feed the
 * research engine. The REAL automation drives the browser with human-like
 * mouse/keyboard — this script only reads what's already rendered.
 */

(function detectLeadSignals() {
  const signals = {
    url: location.href,
    title: document.title,
    // Naive scrape just to prove the wiring; real extraction comes later.
    emails: Array.from(
      new Set((document.body?.innerText || '').match(/[\w.+-]+@[\w-]+\.[\w.-]+/g) || []),
    ).slice(0, 5),
  };

  // In a real build this would post back to the background worker.
  console.debug('[LeadHunter Companion] page signals (stub):', signals);
})();
