#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const file = process.argv[2];
if (!file) {
  console.error('Usage: node emit_write_range_args.cjs <payload.json>');
  process.exit(1);
}
const p = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8'));
process.stdout.write(
  JSON.stringify({
    spreadsheetId: p.spreadsheetId,
    sheet: p.sheet,
    cells: p.cells,
    values: p.values,
  })
);
