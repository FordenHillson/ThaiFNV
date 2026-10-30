#!/usr/bin/env python3
"""Print write_range arguments JSON for batch index 0-8 (stdout)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(
    r"C:\Users\saetanpee\AppData\Local\Cursor\AgentStores\cursor_agent_stores"
    r"\f277bb1f-18c1-446d-97ec-8f94cb76d6fd\files\mcp_invoke"
)


def main() -> None:
    idx = int(sys.argv[1])
    path = BASE / f"_batch{idx}.json"
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    sys.stdout.write(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
