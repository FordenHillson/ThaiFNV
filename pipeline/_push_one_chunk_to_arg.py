#!/usr/bin/env python3
"""Prepare one chunk into _cursor_mcp_arg.json for MCP write_range."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"
OUT = BASE / "_cursor_mcp_arg.json"
SPREADSHEET = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"


def load(name: str) -> dict:
    path = BASE / name
    if name == "FNV_Notes_F967_G1020.json":
        raw = json.load(path.open(encoding="utf-8"))
        return {
            "spreadsheetId": SPREADSHEET,
            "sheet": raw["sheet"],
            "cells": raw["cells"],
            "values": raw["values"],
        }
    return json.load(path.open(encoding="utf-8"))


def main() -> None:
    name = sys.argv[1]
    d = load(name)
    OUT.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print(d["cells"], len(d["values"]))


if __name__ == "__main__":
    main()
