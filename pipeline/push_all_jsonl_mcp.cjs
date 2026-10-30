#!/usr/bin/env node
/**
 * Push all lines in all_args.jsonl via write_range.
 * Requires MCP proxy auth — when REST 401, prints MCP_COMMAND lines for agent.
 */
const fs = require('fs');
const path = require('path');

const jsonl = path.resolve(
  process.env.PUSH_JSONL ||
    'C:/Users/saetanpee/AppData/Local/Cursor/AgentStores/cursor_agent_stores/f277bb1f-18c1-446d-97ec-8f94cb76d6fd/files/push_items/all_args.jsonl'
);
const MCP_URL = 'https://api.cursor.com/rest-mcp/google-sheets/mcp';
const start = parseInt(process.argv[2] || '0', 10);
const end = process.argv[3] ? parseInt(process.argv[3], 10) : undefined;

async function mcpCall(args, retries = 3) {
  const body = {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: { name: 'write_range', arguments: args },
  };
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.CURSOR_REQUEST_ID) headers['x-cursor-auth'] = process.env.CURSOR_REQUEST_ID;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const res = await fetch(MCP_URL, { method: 'POST', headers, body: JSON.stringify(body) });
    const text = await res.text();
    if (res.status === 429 && attempt < retries) {
      await new Promise((r) => setTimeout(r, 60000));
      continue;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    return JSON.parse(text);
  }
  throw new Error('max retries');
}

async function main() {
  const lines = fs.readFileSync(jsonl, 'utf8').trim().split('\n');
  const last = end === undefined ? lines.length - 1 : Math.min(end, lines.length - 1);
  const log = { ok: [], fail: [] };
  for (let i = start; i <= last; i++) {
    const args = JSON.parse(lines[i]);
    const label = `${i}:${args.cells}`;
    try {
      const out = await mcpCall(args);
      log.ok.push({ index: i, cells: args.cells, rows: args.values.length, out });
      console.log('OK', label);
      await new Promise((r) => setTimeout(r, 300));
    } catch (e) {
      log.fail.push({ index: i, cells: args.cells, error: String(e.message || e) });
      console.error('FAIL', label, e.message || e);
      console.log('MCP_COMMAND', JSON.stringify({ tool: 'write_range', arguments: args }));
    }
  }
  const summary = path.join(path.dirname(jsonl), '_push_jsonl_summary.json');
  fs.writeFileSync(summary, JSON.stringify(log, null, 2));
  console.log('SUMMARY', log.ok.length, 'ok', log.fail.length, 'fail');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
