#!/usr/bin/env python3
"""Emit write_range args JSON for one push batch file (stdout)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PUSH = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_ai_notes" / "push"
SPREADSHEET = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"


def main() -> None:
    name = sys.argv[1]
    text = (PUSH / name).read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    raw = json.loads(text)
    out = {
        "spreadsheetId": SPREADSHEET,
        "sheet": raw["sheet"],
        "cells": raw["cells"],
        "values": raw["values"],
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
