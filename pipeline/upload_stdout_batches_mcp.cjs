#!/usr/bin/env node
/**
 * Upload _stdout_{start..end}.json via Cursor Google Sheets MCP REST proxy.
 * Usage: node upload_stdout_batches_mcp.cjs [start] [end]
 */
const fs = require('fs');
const path = require('path');

const dir = path.resolve(
  __dirname,
  '../extracted/sheets/from_google/_push_batches/mini/_arg_chunks'
);
const start = parseInt(process.argv[2] || '1', 10);
const end = parseInt(process.argv[3] || '15', 10);
const MCP_URL = 'https://api.cursor.com/rest-mcp/google-sheets/mcp';

async function mcpCall(toolName, args) {
  const body = {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: { name: toolName, arguments: args },
  };
  const headers = {
    'Content-Type': 'application/json',
  };
  if (process.env.CURSOR_REQUEST_ID) {
    headers['x-cursor-auth'] = process.env.CURSOR_REQUEST_ID;
  }
  const res = await fetch(MCP_URL, { method: 'POST', headers, body: JSON.stringify(body) });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 500)}`);
  }
  return JSON.parse(text);
}

async function main() {
  const log = { ok: [], fail: [] };
  let rows = 0;
  for (let i = start; i <= end; i++) {
    const fp = path.join(dir, `_stdout_${i}.json`);
    let t = fs.readFileSync(fp, 'utf8');
    if (t.charCodeAt(0) === 0xfeff) t = t.slice(1);
    const args = JSON.parse(t);
    const label = `_stdout_${i}.json ${args.cells}`;
    try {
      const out = await mcpCall('write_range', args);
      const n = args.values.length;
      rows += n;
      log.ok.push({ file: label, rows: n, out });
      console.log('OK', label, n, 'rows');
    } catch (e) {
      log.fail.push({ file: label, error: String(e.message || e) });
      console.error('FAIL', label, e.message || e);
    }
  }
  const summaryPath = path.join(dir, '_upload_mcp_summary.json');
  fs.writeFileSync(summaryPath, JSON.stringify({ rows, log }, null, 2));
  console.log('TOTAL_ROWS', rows, 'FAILURES', log.fail.length);
  process.exit(log.fail.length ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
