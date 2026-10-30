#!/usr/bin/env python3
"""Load batch payload JSON and print compact summary lines for MCP push verification."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"
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


def load_batch(name: str) -> dict:
    path = BASE / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: _mcp_push_runner.py <batch_filename>")
        sys.exit(2)
    data = load_batch(sys.argv[1])
    out = {
        "spreadsheetId": "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE",
        "sheet": data["sheet"],
        "cells": data["cells"],
        "values": data["values"],
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
