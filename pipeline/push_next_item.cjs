#!/usr/bin/env node
/** Print next pending push_items args JSON; mark done on --complete <file> */
const fs = require('fs');
const path = require('path');

const ITEMS_DIR = path.resolve(
  process.env.PUSH_ITEMS_DIR ||
    'C:/Users/saetanpee/AppData/Local/Cursor/AgentStores/cursor_agent_stores/f277bb1f-18c1-446d-97ec-8f94cb76d6fd/files/push_items'
);
const MANIFEST = path.join(ITEMS_DIR, 'manifest.json');

const complete = process.argv.indexOf('--complete');
if (complete !== -1) {
  const file = process.argv[complete + 1];
  const manifest = JSON.parse(fs.readFileSync(MANIFEST, 'utf8'));
  const m = manifest.find((x) => x.file === file);
  if (m) m.skip = true;
  fs.writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2));
  console.log('MARKED', file);
  process.exit(0);
}

const manifest = JSON.parse(fs.readFileSync(MANIFEST, 'utf8'));
const next = manifest.find((x) => !x.skip);
if (!next) {
  console.log('NONE');
  process.exit(0);
}
const base = next.file.replace('.json', '');
const args = JSON.parse(
  fs.readFileSync(path.join(ITEMS_DIR, base + '.json'), 'utf8')
);
console.log('FILE', next.file);
console.log(JSON.stringify(args));
