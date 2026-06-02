'use strict';

/**
 * csv — tiny dependency-free CSV writer (RFC-4180 quoting).
 */

const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_COLUMNS = ['name', 'business', 'email', 'phone', 'source', 'hook', 'score', 'website'];

/**
 * Serialize rows to a CSV string.
 * @param {Array<object>} rows
 * @param {string[]} [columns]
 * @returns {string}
 */
function toCsv(rows, columns = DEFAULT_COLUMNS) {
  const lines = [columns.map(escapeCell).join(',')];
  for (const row of rows) {
    lines.push(columns.map((c) => escapeCell(row[c])).join(','));
  }
  return lines.join('\n') + '\n';
}

/**
 * Write rows to a CSV file.
 * @param {string} filePath
 * @param {Array<object>} rows
 * @param {string[]} [columns]
 * @returns {string} filePath
 */
function writeCsv(filePath, rows, columns = DEFAULT_COLUMNS) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, toCsv(rows, columns), 'utf8');
  return filePath;
}

function escapeCell(value) {
  if (value === null || value === undefined) return '';
  const s = String(value);
  if (/[",\n\r]/.test(s)) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

module.exports = { toCsv, writeCsv, DEFAULT_COLUMNS };
