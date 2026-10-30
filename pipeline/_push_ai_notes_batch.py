#!/usr/bin/env python3
"""Print write_range args JSON for push batch files (one path per argv)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SP = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"
BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_ai_notes" / "push" / "_mcp_args"


def main() -> None:
    for name in sys.argv[1:]:
        path = BASE / name
        raw = json.loads(path.read_text(encoding="utf-8"))
        out = {
            "spreadsheetId": SP,
            "sheet": raw["sheet"],
            "cells": raw["cells"],
            "values": raw["values"],
        }
        print(json.dumps({"file": name, "args": out, "rows": len(out["values"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
