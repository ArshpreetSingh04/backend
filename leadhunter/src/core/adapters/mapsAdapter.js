'use strict';

/**
 * mapsAdapter — Google Maps / Places style business discovery. STUB.
 *
 * This path needs a Places API key (or an authenticated, ToS-compliant Maps
 * session) that we don't have. Rather than fabricate anything, it returns
 * nothing and flags the gap. The real web-search path stays fully functional.
 *
 * [needs-key:maps]
 */

const NEEDS_KEY = 'maps';

/**
 * @param {object} _profile
 * @returns {Promise<Array>} always empty until a key/session is provided
 */
async function discover(_profile) {
  // [needs-key:maps] Intentionally no results — never fake leads.
  return [];
}

module.exports = { discover, NEEDS_KEY };
