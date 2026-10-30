#!/usr/bin/env python3
"""Load mcp_invoke JSON files and print one line per batch for agent MCP write_range."""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(
    r"C:\Users\saetanpee\AppData\Local\Cursor\AgentStores\cursor_agent_stores"
    r"\f277bb1f-18c1-446d-97ec-8f94cb76d6fd\files\mcp_invoke"
)
FILES = [
    "FNV_Notes_F167_G266.json",
    "FNV_Notes_F267_G366.json",
    "FNV_Notes_F367_G466.json",
    "FNV_Notes_F467_G566.json",
    "FNV_Notes_F567_G666.json",
    "FNV_Notes_F667_G766.json",
    "FNV_Notes_F767_G866.json",
    "FNV_Notes_F867_G966.json",
    "FNV_Notes_F967_G1020.json",
]


def load(name: str) -> dict:
    path = INVOKE / name
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "--dump":
        idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        name = FILES[idx]
        sys.stdout.write(json.dumps(load(name), ensure_ascii=False))
        return
    total = 0
    for name in FILES:
        d = load(name)
        total += len(d["values"])
        print(f"{name}\t{d['cells']}\t{len(d['values'])}")
    print(f"TOTAL_ROWS\t{total}")


if __name__ == "__main__":
    main()
