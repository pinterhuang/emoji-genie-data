#!/usr/bin/env node
/**
 * Moves N kaomojis from reserve.json → kaomoji-bundle.json.
 *
 * Use this for scheduled monthly drops:
 *   node scripts/promote-from-reserve.js --count 100
 *   node scripts/promote-from-reserve.js --count 50 --category festival
 *
 * Selection logic:
 *   - Picks oldest reserved entries first (FIFO based on reserve.json ordering)
 *   - Filters by --category if provided
 *   - Skips entries whose id already exists in the live bundle
 *
 * After promotion: bump version + commit. The release.yml workflow handles bumping.
 *
 * Usage:
 *   node scripts/promote-from-reserve.js --count 100              # any category
 *   node scripts/promote-from-reserve.js --count 30 --category festival
 *   node scripts/promote-from-reserve.js --count 50 --dry-run     # preview
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BUNDLE = path.join(ROOT, 'kaomoji-bundle.json');
const RESERVE = path.join(ROOT, 'reserve.json');

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  if (i === -1) return fallback;
  return process.argv[i + 1];
}
function flag(name) {
  return process.argv.includes(`--${name}`);
}

const count = parseInt(arg('count', '100'), 10);
const filterCategory = arg('category', null);
const dryRun = flag('dry-run');

if (!count || count <= 0) {
  console.error('Usage: --count <N> [--category <id>] [--dry-run]');
  process.exit(1);
}

const bundle = JSON.parse(fs.readFileSync(BUNDLE, 'utf8'));
const reserve = JSON.parse(fs.readFileSync(RESERVE, 'utf8'));

const liveIds = new Set(bundle.kaomojis.map(k => k.id));
const liveTexts = new Set(bundle.kaomojis.map(k => k.t));

const promoted = [];
const remaining = [];

for (const entry of reserve.kaomojis) {
  const eligible =
    !liveIds.has(entry.id) &&
    !liveTexts.has(entry.t) &&
    (!filterCategory || entry.c === filterCategory);
  if (eligible && promoted.length < count) {
    promoted.push(entry);
  } else {
    remaining.push(entry);
  }
}

console.log(`Selected ${promoted.length} entries to promote` +
  (filterCategory ? ` (category: ${filterCategory})` : '') + '.');

if (promoted.length === 0) {
  console.log('Nothing to promote. Exiting.');
  process.exit(0);
}

// Sample preview
console.log('\nSample (first 5):');
promoted.slice(0, 5).forEach(p => console.log(`  ${p.id}  [${p.c}]  ${p.t}`));

if (dryRun) {
  console.log('\n--dry-run: no files written.');
  process.exit(0);
}

// Append to bundle, bump version, refresh date
bundle.version = (bundle.version || 1) + 1;
bundle.publishedAt = new Date().toISOString().slice(0, 10);
bundle.kaomojis.push(...promoted);

reserve.kaomojis = remaining;
reserve.count = remaining.length;

fs.writeFileSync(BUNDLE, JSON.stringify(bundle, null, 2) + '\n');
fs.writeFileSync(RESERVE, JSON.stringify(reserve, null, 2) + '\n');

console.log(`\n✓ Bundle bumped to v${bundle.version}`);
console.log(`  Live kaomojis: ${bundle.kaomojis.length}`);
console.log(`  Reserve remaining: ${remaining.length}`);
