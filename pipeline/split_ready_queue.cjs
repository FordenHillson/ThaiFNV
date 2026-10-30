#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const dir = path.resolve(
  __dirname,
  '../extracted/sheets/from_google/_push_batches/mini/_upload_queue'
);
const outDir = path.join(dir, '_split');
fs.mkdirSync(outDir, { recursive: true });
for (let n = 9; n <= 15; n++) {
  const id = String(n).padStart(2, '0');
  const a = JSON.parse(fs.readFileSync(path.join(dir, `_ready_${id}.json`), 'utf8'));
  const start = parseInt(a.cells.replace(/\D/g, ''), 10);
  for (let j = 0; j < a.values.length; j += 10) {
    const chunk = {
      spreadsheetId: a.spreadsheetId,
      sheet: a.sheet,
      cells: 'F' + (start + j),
      values: a.values.slice(j, j + 10),
    };
    fs.writeFileSync(path.join(outDir, `${id}_${j}.json`), JSON.stringify(chunk));
  }
}
console.log('ok');
