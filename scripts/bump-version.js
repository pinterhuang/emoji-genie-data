#!/usr/bin/env node
/**
 * Auto-bumps the bundle's `version` field by 1, refreshes `publishedAt`,
 * and writes the file back. Used by the release GitHub Action on push to main
 * when the kaomoji content has changed.
 *
 * Skipping logic: if `--check` is passed, only prints what *would* happen
 * (used by PR action to remind contributors).
 *
 * Usage:
 *   node scripts/bump-version.js          # bump in place
 *   node scripts/bump-version.js --check  # dry run
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BUNDLE = path.join(ROOT, 'kaomoji-bundle.json');
const isCheck = process.argv.includes('--check');

const bundle = JSON.parse(fs.readFileSync(BUNDLE, 'utf8'));
const oldVer = bundle.version;
const newVer = oldVer + 1;
const today = new Date().toISOString().slice(0, 10);

bundle.version = newVer;
bundle.publishedAt = today;

if (isCheck) {
  console.log(`Would bump v${oldVer} → v${newVer} (publishedAt: ${today})`);
  process.exit(0);
}

// Preserve trailing newline + 2-space indent to match repo convention.
fs.writeFileSync(BUNDLE, JSON.stringify(bundle, null, 2) + '\n');
console.log(`Bumped v${oldVer} → v${newVer} (publishedAt: ${today})`);
