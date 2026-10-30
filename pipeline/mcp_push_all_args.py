#!/usr/bin/env python3
"""Load _mcp_args/*.json and invoke write_range via stdin protocol for agent batching."""
from __future__ import annotations

import json
import sys
from pathlib import Path

MCP_DIR = (
    Path(__file__).resolve().parents[1]
    / "extracted"
    / "sheets"
    / "from_google"
    / "_ai_notes"
    / "push"
    / "_mcp_args"
)


def main() -> None:
    names = sorted(MCP_DIR.glob("F*.json"))
    for path in names:
        data = json.loads(path.read_text(encoding="utf-8"))
        out = {
            "file": path.name,
            "args": {
                "spreadsheetId": data["spreadsheetId"],
                "sheet": data["sheet"],
                "cells": data["cells"],
                "values": data["values"],
            },
            "rows": len(data["values"]),
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
