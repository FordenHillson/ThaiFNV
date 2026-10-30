#!/usr/bin/env node
/** Print write_range args for upload queue item q_XX (XX = 04..15) */
const fs = require('fs');
const path = require('path');
const id = process.argv[2];
if (!id) {
  console.error('Usage: node upload_queue_item.cjs <04..15>');
  process.exit(1);
}
const fp = path.resolve(
  __dirname,
  '../extracted/sheets/from_google/_push_batches/mini/_upload_queue',
  `q_${id}.json`
);
let t = fs.readFileSync(fp, 'utf8');
if (t.charCodeAt(0) === 0xfeff) t = t.slice(1);
process.stdout.write(t);
