#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const jsonl = path.resolve(
  process.env.PUSH_JSONL ||
    'C:/Users/saetanpee/AppData/Local/Cursor/AgentStores/cursor_agent_stores/f277bb1f-18c1-446d-97ec-8f94cb76d6fd/files/push_items/all_args.jsonl'
);
const idx = parseInt(process.argv[2] || '0', 10);
const lines = fs.readFileSync(jsonl, 'utf8').trim().split('\n');
if (idx >= lines.length) {
  console.log('DONE');
  process.exit(0);
}
console.log('IDX', idx, 'OF', lines.length);
console.log(lines[idx]);
