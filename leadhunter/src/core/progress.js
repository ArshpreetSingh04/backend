'use strict';

/**
 * progress — a tiny helper to emit structured progress events during a hunt.
 *
 * Event shape: { phase, message, data, t }
 *   phase: one of PHASES (parsing-prompt, searching, business-found,
 *          qualifying, enriching, persisted, done, error)
 *
 * The returned function is always safe to call (no-op if no sink is given) and
 * never throws into the run — a broken UI listener must not break a hunt.
 */

const PHASES = Object.freeze({
  PARSING: 'parsing-prompt',
  SEARCHING: 'searching',
  BUSINESS_FOUND: 'business-found',
  QUALIFYING: 'qualifying',
  ENRICHING: 'enriching',
  PERSISTED: 'persisted',
  DONE: 'done',
  ERROR: 'error',
});

/**
 * @param {(evt:{phase:string,message:string,data:object|null,t:number})=>void} [onProgress]
 * @returns {(phase:string, message?:string, data?:object)=>void}
 */
function makeProgress(onProgress) {
  const sink = typeof onProgress === 'function' ? onProgress : null;
  return function progress(phase, message, data) {
    if (!sink) return;
    try {
      sink({ phase, message: message || '', data: data || null, t: Date.now() });
    } catch {
      /* never let a listener error break the run */
    }
  };
}

module.exports = { makeProgress, PHASES };
