#!/usr/bin/env node
/**
 * Upload FNV_Notes AI push JSON batches via Cursor Google Sheets MCP REST proxy.
 */
const fs = require('fs');
const path = require('path');

const dir = path.resolve(__dirname, '../extracted/sheets/from_google/_ai_notes/push');
const MCP_URL = 'https://api.cursor.com/rest-mcp/google-sheets/mcp';
const SPREADSHEET = '1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE';

async function mcpCall(toolName, args, retries = 3) {
  const body = {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: { name: toolName, arguments: args },
  };
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.CURSOR_REQUEST_ID) {
    headers['x-cursor-auth'] = process.env.CURSOR_REQUEST_ID;
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
    .filter((f) => f.endsWith('.json') && !f.startsWith('_'))
    .sort();
  const log = { ok: [], fail: [] };
  let rows = 0;
  for (const name of files) {
    if (skip.has(name)) continue;
    let t = fs.readFileSync(path.join(dir, name), 'utf8');
    if (t.charCodeAt(0) === 0xfeff) t = t.slice(1);
    const raw = JSON.parse(t);
    const args = {
      spreadsheetId: SPREADSHEET,
      sheet: raw.sheet,
      cells: raw.cells,
      values: raw.values,
    };
    const label = `${name} ${args.cells}`;
    try {
      const out = await mcpCall('write_range', args);
      const n = args.values.length;
      rows += n;
      log.ok.push({ file: name, cells: args.cells, rows: n, out });
      console.log('OK', label, n, 'rows');
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
