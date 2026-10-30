#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const dir = path.resolve(
  __dirname,
  '../extracted/sheets/from_google/_push_batches/mini/_arg_chunks'
);
const start = parseInt(process.argv[2] || '2', 10);
const end = parseInt(process.argv[3] || '15', 10);
for (let i = start; i <= end; i++) {
  let t = fs.readFileSync(path.join(dir, `_stdout_${i}.json`), 'utf8');
  if (t.charCodeAt(0) === 0xfeff) t = t.slice(1);
  process.stdout.write(`---BATCH---${i}\n`);
  process.stdout.write(t);
  process.stdout.write('\n');
}
