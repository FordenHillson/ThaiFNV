#!/usr/bin/env python3
"""Emit one JSON line per chunk for agent MCP write_range (stdout)."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"
SPREADSHEET = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"


def load_chunk(name: str) -> dict:
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
    names = sorted(BASE.glob("_mcp_chunk_*.json"))
    names = [p.name for p in names]
    names.append("FNV_Notes_F967_G1020.json")
    # skip already done if needed — agent pushes all listed
    for name in names:
        d = load_chunk(name)
        sys.stdout.write(json.dumps(d, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import sys

    main()
