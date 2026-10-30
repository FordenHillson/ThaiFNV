#!/usr/bin/env node
/**
 * Push all push_items/*.json via in-process fetch to Cursor MCP when auth works.
 * Fallback: print JSONL for agent CallDynamicTool (one object per line).
 * Usage: node push_items_mcp_runner.cjs [--dry-run]
 */
const fs = require('fs');
const path = require('path');

const ITEMS_DIR = path.resolve(
  process.env.PUSH_ITEMS_DIR ||
    'C:/Users/saetanpee/AppData/Local/Cursor/AgentStores/cursor_agent_stores/f277bb1f-18c1-446d-97ec-8f94cb76d6fd/files/push_items'
);
const MANIFEST = path.join(ITEMS_DIR, 'manifest.json');
const SUMMARY = path.join(
  path.dirname(ITEMS_DIR),
  'push_results.json'
);
const MCP_URL = 'https://api.cursor.com/rest-mcp/google-sheets/mcp';
const dryRun = process.argv.includes('--dry-run');

async function mcpCall(args, retries = 3) {
  const body = {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: { name: 'write_range', arguments: args },
  };
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.CURSOR_SESSION_TOKEN) {
    headers['x-cursor-auth'] = process.env.CURSOR_SESSION_TOKEN;
  } else if (process.env.CURSOR_REQUEST_ID) {
    headers['x-cursor-auth'] = process.env.CURSOR_REQUEST_ID;
  }
  for (let attempt = 0; attempt <= retries; attempt++) {
    const res = await fetch(MCP_URL, { method: 'POST', headers, body: JSON.stringify(body) });
    const text = await res.text();
    if (res.status === 429 && attempt < retries) {
      await new Promise((r) => setTimeout(r, 60000));
      continue;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 300)}`);
    return JSON.parse(text);
  }
  throw new Error('max retries');
}

async function main() {
  const manifest = JSON.parse(fs.readFileSync(MANIFEST, 'utf8'));
  const todo = manifest.filter((m) => !m.skip);
  const log = { ok: [], fail: [] };
  if (dryRun) {
    for (const m of todo) console.log(JSON.stringify({ file: m.file, args: JSON.parse(fs.readFileSync(path.join(ITEMS_DIR, m.file.replace('.json', '') + '.json'), 'utf8')) }));
    return;
  }
  for (const m of todo) {
    const base = m.file.replace('.json', '');
    const args = JSON.parse(fs.readFileSync(path.join(ITEMS_DIR, base + '.json'), 'utf8'));
    try {
      const out = await mcpCall(args);
      log.ok.push({ file: m.file, cells: args.cells, rows: args.values.length, out });
      console.log('OK', m.file, args.cells);
      await new Promise((r) => setTimeout(r, 250));
    } catch (e) {
      log.fail.push({ file: m.file, cells: args.cells, error: String(e.message || e) });
      console.error('FAIL', m.file, e.message || e);
    }
  }
  fs.writeFileSync(SUMMARY, JSON.stringify(log, null, 2));
  console.log('DONE ok', log.ok.length, 'fail', log.fail.length);
  process.exit(log.fail.length ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
