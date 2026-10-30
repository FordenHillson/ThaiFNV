#!/usr/bin/env python3
"""Load batch payload JSON and print as single line for MCP (stdout)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"


def main() -> None:
    idx = int(sys.argv[1])
    path = BASE / f"_mcp_payload_{idx}.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    # Only fields write_range needs
    out = {
        "spreadsheetId": data["spreadsheetId"],
        "sheet": data["sheet"],
        "cells": data["cells"],
        "values": data["values"],
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
