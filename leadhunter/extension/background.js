'use strict';

/**
 * LeadHunter Companion — background service worker. STUB.
 *
 * Eventual role: bridge between the desktop app and the live browser session so
 * the research engine can hand off / receive page context, and so the user can
 * one-click "capture this business as a lead" from any page.
 *
 * [needs-key:native-host] Native messaging host to talk to the desktop app.
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log('[LeadHunter Companion] installed (stub).');
});

// Placeholder message handler for the future desktop <-> extension channel.
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.type === 'PING') {
    sendResponse({ type: 'PONG', from: 'leadhunter-companion', stub: true });
  }
  return true;
});
