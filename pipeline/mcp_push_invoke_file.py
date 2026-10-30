#!/usr/bin/env python3
"""Load one *_invoke.json and call Google Sheets MCP write_range via agent-only path.

When run from Cursor agent shell, REST MCP auth fails (401). This script prints
args JSON to stdout for CallDynamicTool write_range, or with --summary only stats.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    if sys.argv[-1] == "--summary":
        d = json.loads(text)
        print(json.dumps({"cells": d["cells"], "rows": len(d["values"])}, ensure_ascii=False))
        return
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
