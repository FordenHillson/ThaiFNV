#!/usr/bin/env node
/**
 * Emit write_range arguments for each mini batch (for agent MCP upload).
 * Usage: node upload_mini_batches_loop.cjs [startIndex] [count]
 */
const fs = require('fs');
const path = require('path');

const allPath = path.resolve(
  __dirname,
  '../extracted/sheets/from_google/_push_batches/mini/_all_write_args.json'
);
const arr = JSON.parse(fs.readFileSync(allPath, 'utf8'));
const start = parseInt(process.argv[2] || '0', 10);
const count = parseInt(process.argv[3] || String(arr.length - start), 10);
const slice = arr.slice(start, start + count);
for (const item of slice) {
  process.stdout.write(`---BATCH---${item.file}\n`);
  process.stdout.write(JSON.stringify(item.args));
  process.stdout.write('\n');
}
