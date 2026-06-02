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

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const prompt = promptEl.value.trim();
  if (!prompt) {
    setStatus('Type what leads you want first.', 'error');
    return;
  }

  setBusy(true);
  setStatus('Planning the search and gathering leads…');

  const resp = await window.leadhunter.hunt(prompt);

  if (!resp.ok) {
    setStatus(resp.error || 'Something went wrong.', 'error');
    setBusy(false);
    return;
  }

  const { leads, stats, csvPath } = resp.result;
  renderLeads(leads);
  setStatus(
    `Found ${stats.found} • saved ${stats.inserted} new (${stats.skipped} dupes skipped) • CSV: ${csvPath}`,
    'ok',
  );
  setBusy(false);
});

openDataBtn.addEventListener('click', () => window.leadhunter.openDataDir());

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
