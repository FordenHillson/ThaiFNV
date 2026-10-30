#!/usr/bin/env python3
"""Write write_range args for chunk N to agent store _next_mcp.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"
OUT = Path(
    r"C:\Users\saetanpee\AppData\Local\Cursor\AgentStores\cursor_agent_stores"
    r"\f277bb1f-18c1-446d-97ec-8f94cb76d6fd\files\mcp_invoke\_next_mcp.json"
)


def main() -> None:
    name = sys.argv[1]
    path = BASE / name
    if name == "FNV_Notes_F967_G1020.json":
        raw = json.load(path.open(encoding="utf-8"))
        d = {
            "spreadsheetId": "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE",
            "sheet": raw["sheet"],
            "cells": raw["cells"],
            "values": raw["values"],
        }
    else:
        d = json.load(path.open(encoding="utf-8"))
    OUT.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print(d["cells"], len(d["values"]))


if __name__ == "__main__":
    main()
