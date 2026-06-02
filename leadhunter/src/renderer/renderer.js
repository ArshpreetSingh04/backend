'use strict';

/* Renderer: wires the single "Find Leads" box to the pipeline (via the
   preload bridge) and paints the results table. No Node access here. */

const form = document.getElementById('huntForm');
const promptEl = document.getElementById('prompt');
const submitBtn = document.getElementById('submit');
const statusEl = document.getElementById('status');
const tbody = document.getElementById('resultsBody');
const emptyEl = document.getElementById('empty');
const openDataBtn = document.getElementById('openData');
const realToggle = document.getElementById('realToggle');
const modeHint = document.getElementById('mode-hint');
const progressEl = document.getElementById('progress');

// Reflect the chosen mode in the hint text.
realToggle.addEventListener('change', () => {
  modeHint.textContent = realToggle.checked
    ? 'Real mode — drives a real browser to research the open web (slower).'
    : 'Mock mode — safe, instant sample leads.';
});

// Icons per progress phase, for a readable live activity log.
const PHASE_ICON = {
  'parsing-prompt': '📝',
  searching: '🔎',
  'business-found': '🏢',
  qualifying: '⚖️',
  enriching: '✉️',
  persisted: '💾',
  done: '✅',
  error: '⚠️',
};

let unsubscribeProgress = null;

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const prompt = promptEl.value.trim();
  if (!prompt) {
    setStatus('Type what leads you want first.', 'error');
    return;
  }

  const mode = realToggle.checked ? 'real' : 'mock';
  setBusy(true);
  clearProgress();
  setStatus(mode === 'real' ? 'Starting the real research engine…' : 'Gathering mock leads…');

  // Subscribe to live progress for this run.
  if (unsubscribeProgress) unsubscribeProgress();
  unsubscribeProgress = window.leadhunter.onProgress(addProgress);

  const resp = await window.leadhunter.hunt(prompt, mode);

  if (unsubscribeProgress) {
    unsubscribeProgress();
    unsubscribeProgress = null;
  }

  if (!resp.ok) {
    setStatus(resp.error || 'Something went wrong.', 'error');
    setBusy(false);
    return;
  }

  const { leads, stats, csvPath, engine } = resp.result;
  renderLeads(leads);
  setStatus(
    `[${engine}] Found ${stats.found} • saved ${stats.inserted} new (${stats.skipped} dupes skipped) • CSV: ${csvPath}`,
    'ok',
  );
  setBusy(false);
});

openDataBtn.addEventListener('click', () => window.leadhunter.openDataDir());

function clearProgress() {
  progressEl.replaceChildren();
}

function addProgress(evt) {
  const li = document.createElement('li');
  li.className = 'progress-item phase-' + evt.phase;
  const icon = document.createElement('span');
  icon.className = 'p-icon';
  icon.textContent = PHASE_ICON[evt.phase] || '•';
  const text = document.createElement('span');
  text.textContent = evt.message || evt.phase;
  li.append(icon, text);
  progressEl.append(li);
  progressEl.scrollTop = progressEl.scrollHeight;
}

function renderLeads(leads) {
  tbody.replaceChildren();
  if (!leads || leads.length === 0) {
    emptyEl.classList.remove('hidden');
    return;
  }
  emptyEl.classList.add('hidden');

  for (const lead of leads) {
    const tr = document.createElement('tr');
    tr.append(
      cell(lead.name),
      cell(lead.business),
      cell(lead.website),
      cell(lead.email),
      cell(lead.phone),
      cell(lead.source),
      cell(lead.hook),
      scoreCell(lead.score),
    );
    tbody.append(tr);
  }
}

function cell(text) {
  const td = document.createElement('td');
  td.textContent = text == null ? '' : String(text);
  return td;
}

function scoreCell(score) {
  const td = document.createElement('td');
  td.className = 'num';
  const span = document.createElement('span');
  span.className = 'score' + (Number(score) < 75 ? ' mid' : '');
  span.textContent = score == null ? '' : String(score);
  td.append(span);
  return td;
}

function setStatus(msg, kind) {
  statusEl.textContent = msg;
  statusEl.className = 'status' + (kind ? ' ' + kind : '');
}

function setBusy(busy) {
  submitBtn.disabled = busy;
  submitBtn.textContent = busy ? 'Hunting…' : 'Find Leads';
}
