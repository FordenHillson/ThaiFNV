#!/usr/bin/env python3
"""Print write_range args JSON lines for each push batch (agent MCP loop)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PUSH = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_ai_notes" / "push"
SPREADSHEET = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"


def load_batch(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    raw = json.loads(text)
    return {
        "spreadsheetId": SPREADSHEET,
        "sheet": raw["sheet"],
        "cells": raw["cells"],
        "values": raw["values"],
    }


def main() -> None:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 999
    files = sorted(PUSH.glob("F*.json"))
    for i, path in enumerate(files):
        if i < start or i >= end:
            continue
        d = load_batch(path)
        row = {"file": path.name, "args": d}
        sys.stdout.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
