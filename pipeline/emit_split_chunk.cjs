#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const name = process.argv[2];
if (!name) process.exit(1);
const fp = path.resolve(
  __dirname,
  '../extracted/sheets/from_google/_push_batches/mini/_upload_queue/_split',
  name
);
process.stdout.write(fs.readFileSync(fp, 'utf8'));
