#!/usr/bin/env node
/**
 * Agent helper: push all remaining push_items using write_range args files.
 * This script ONLY validates payloads and writes push_log.jsonl;
 * MCP writes must be done by agent CallDynamicTool per line in push_mcp_commands.jsonl
 *
 * Run: node push_remaining_via_node_read.cjs --emit-commands
 */
const fs = require('fs');
const path = require('path');

const ITEMS_DIR = path.resolve(
  process.env.PUSH_ITEMS_DIR ||
    'C:/Users/saetanpee/AppData/Local/Cursor/AgentStores/cursor_agent_stores/f277bb1f-18c1-446d-97ec-8f94cb76d6fd/files/push_items'
);
const MANIFEST = path.join(ITEMS_DIR, 'manifest.json');
const COMMANDS = path.join(ITEMS_DIR, 'push_mcp_commands.jsonl');

function main() {
  const manifest = JSON.parse(fs.readFileSync(MANIFEST, 'utf8'));
  const todo = manifest.filter((x) => !x.skip);
  const lines = [];
  for (const m of todo) {
    const base = m.file.replace('.json', '');
    const args = JSON.parse(
      fs.readFileSync(path.join(ITEMS_DIR, base + '.json'), 'utf8')
    );
    lines.push(JSON.stringify({ file: m.file, tool: 'write_range', arguments: args }));
  }
  fs.writeFileSync(COMMANDS, lines.join('\n') + '\n');
  console.log('WROTE', lines.length, 'commands to', COMMANDS);
}

main();
