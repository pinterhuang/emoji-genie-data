#!/usr/bin/env node
/**
 * Validates kaomoji-bundle.json against schema.json plus extra invariants
 * (no duplicate ids, no orphan category refs).
 *
 * Zero dependencies — uses only Node built-ins so contributors don't need to npm install.
 *
 * Usage: node scripts/validate.js
 * Exits 0 on success, 1 on any error.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BUNDLE = path.join(ROOT, 'kaomoji-bundle.json');

function fail(msg) {
  console.error(`\u001b[31m✗ ${msg}\u001b[0m`);
  process.exitCode = 1;
}

function pass(msg) {
  console.log(`\u001b[32m✓ ${msg}\u001b[0m`);
}

function readJson(p) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (err) {
    fail(`Failed to parse ${path.basename(p)}: ${err.message}`);
    process.exit(1);
  }
}

const bundle = readJson(BUNDLE);

// 1. Top-level shape.
const requiredTopLevel = ['version', 'categories', 'kaomojis'];
for (const key of requiredTopLevel) {
  if (!(key in bundle)) fail(`Missing top-level field: "${key}"`);
}
if (!Number.isInteger(bundle.version) || bundle.version < 1) {
  fail(`"version" must be a positive integer, got: ${bundle.version}`);
}
if (!Array.isArray(bundle.categories)) fail('"categories" must be an array');
if (!Array.isArray(bundle.kaomojis)) fail('"kaomojis" must be an array');
if (process.exitCode === 1) process.exit(1);

// 2. Category validation.
const catIds = new Set();
const catIdRe = /^[a-z0-9_]+$/;
for (const cat of bundle.categories) {
  for (const k of ['id', 'name', 'icon', 'order']) {
    if (!(k in cat)) fail(`Category missing field "${k}": ${JSON.stringify(cat)}`);
  }
  if (!catIdRe.test(cat.id)) fail(`Category id "${cat.id}" must match ${catIdRe}`);
  if (catIds.has(cat.id)) fail(`Duplicate category id: "${cat.id}"`);
  catIds.add(cat.id);
  if (!Number.isInteger(cat.order) || cat.order < 0) {
    fail(`Category "${cat.id}" has invalid order: ${cat.order}`);
  }
}

// 3. Kaomoji validation.
const kIds = new Set();
const kIdRe = /^[a-zA-Z0-9_-]+$/;
for (const k of bundle.kaomojis) {
  for (const f of ['id', 't', 'c']) {
    if (!(f in k)) fail(`Kaomoji missing field "${f}": ${JSON.stringify(k)}`);
  }
  if (typeof k.id !== 'string' || !kIdRe.test(k.id)) {
    fail(`Kaomoji id "${k.id}" must match ${kIdRe}`);
  }
  if (kIds.has(k.id)) fail(`Duplicate kaomoji id: "${k.id}"`);
  kIds.add(k.id);
  if (typeof k.t !== 'string' || k.t.length === 0) {
    fail(`Kaomoji "${k.id}" has empty text`);
  }
  if (!catIds.has(k.c)) {
    fail(`Kaomoji "${k.id}" references unknown category "${k.c}"`);
  }
  if ('k' in k) {
    if (!Array.isArray(k.k) || !k.k.every(t => typeof t === 'string')) {
      fail(`Kaomoji "${k.id}" has invalid tags`);
    }
  }
  if ('tier' in k && k.tier !== 'free' && k.tier !== 'pro') {
    fail(`Kaomoji "${k.id}" has invalid tier "${k.tier}" (must be "free" or "pro")`);
  }
  if ('availableFrom' in k) {
    if (typeof k.availableFrom !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(k.availableFrom)) {
      fail(`Kaomoji "${k.id}" has invalid availableFrom "${k.availableFrom}" (must be YYYY-MM-DD)`);
    }
  }
}

if (process.exitCode === 1) {
  console.error(`\nValidation failed.`);
  process.exit(1);
}

pass(`Bundle v${bundle.version}: ${bundle.categories.length} categories, ${bundle.kaomojis.length} kaomojis — OK`);
