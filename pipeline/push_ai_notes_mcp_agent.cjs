#!/usr/bin/env node
/**
 * Push AI notes batches via MCP REST with extended Cursor auth headers.
 * Agent should run: node push_ai_notes_mcp_agent.cjs [skipCommaList]
 */
const fs = require('fs');
const path = require('path');

const dir = path.resolve(__dirname, '../extracted/sheets/from_google/_ai_notes/push');
const mcpDir = path.join(dir, '_mcp_args');
const SPREADSHEET = '1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE';
const MCP_URL = 'https://api.cursor.com/rest-mcp/google-sheets/mcp';

function loadArgs(name) {
  const mp = path.join(mcpDir, name);
  if (fs.existsSync(mp)) return JSON.parse(fs.readFileSync(mp, 'utf8'));
  let t = fs.readFileSync(path.join(dir, name), 'utf8');
  if (t.charCodeAt(0) === 0xfeff) t = t.slice(1);
  const raw = JSON.parse(t);
  return {
    spreadsheetId: SPREADSHEET,
    sheet: raw.sheet,
    cells: raw.cells,
    values: raw.values,
  };
}

async function mcpCall(toolName, args, retries = 3) {
  const body = {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: { name: toolName, arguments: args },
  };
  const headers = { 'Content-Type': 'application/json' };
  for (const key of [
    'CURSOR_REQUEST_ID',
    'CURSOR_CONVERSATION_ID',
    'CURSOR_AGENT_AUTH',
    'CURSOR_AUTH_TOKEN',
  ]) {
    if (process.env[key]) headers['x-cursor-auth'] = process.env[key];
  }
  if (process.env.CURSOR_REQUEST_ID) {
    headers['x-cursor-request-id'] = process.env.CURSOR_REQUEST_ID;
  }
  if (process.env.CURSOR_CONVERSATION_ID) {
    headers['x-cursor-conversation-id'] = process.env.CURSOR_CONVERSATION_ID;
  }
  for (let attempt = 0; attempt <= retries; attempt++) {
    const res = await fetch(MCP_URL, { method: 'POST', headers, body: JSON.stringify(body) });
    const text = await res.text();
    if (res.status === 429 && attempt < retries) {
      console.error('429 rate limit, waiting 60s...', args.cells);
      await new Promise((r) => setTimeout(r, 60000));
      continue;
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${text.slice(0, 500)}`);
    }
    return JSON.parse(text);
  }
  throw new Error('max retries');
}

async function main() {
  const skip = new Set((process.argv[2] || '').split(',').filter(Boolean));
  const files = fs
    .readdirSync(dir)
    .filter((f) => /^F\d+\.json$/.test(f))
    .sort();
  const log = { ok: [], fail: [] };
  let rows = 0;
  for (const name of files) {
    if (skip.has(name)) continue;
    const args = loadArgs(name);
    const label = `${name} ${args.cells}`;
    try {
      const out = await mcpCall('write_range', args);
      const n = args.values.length;
      rows += n;
      log.ok.push({ file: name, cells: args.cells, rows: n, out });
      console.log('OK', label, n, 'rows');
      await new Promise((r) => setTimeout(r, 300));
    } catch (e) {
      log.fail.push({ file: name, cells: args.cells, error: String(e.message || e) });
      console.error('FAIL', label, e.message || e);
    }
  }
  const summaryPath = path.join(dir, '_upload_mcp_summary.json');
  fs.writeFileSync(
    summaryPath,
    JSON.stringify({ filesWritten: log.ok.length, rows, log }, null, 2)
  );
  console.log('FILES_WRITTEN', log.ok.length, 'TOTAL_ROWS', rows, 'FAILURES', log.fail.length);
  process.exit(log.fail.length ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
