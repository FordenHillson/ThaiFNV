#!/usr/bin/env node
/** Print write_range args JSON for one arg chunk index */
const fs = require('fs');
const path = require('path');
const i = parseInt(process.argv[2], 10);
const file = path.resolve(
  __dirname,
  '../extracted/sheets/from_google/_push_batches/mini/_arg_chunks',
  `arg_${i}.json`
);
process.stdout.write(fs.readFileSync(file, 'utf8'));
