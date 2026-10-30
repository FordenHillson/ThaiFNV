#!/usr/bin/env python3
"""Print chunk filename and row count (for agent MCP loop)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"


def main() -> None:
    name = sys.argv[1]
    path = BASE / name
    d = json.load(path.open(encoding="utf-8"))
    print(json.dumps({"file": name, "cells": d["cells"], "rows": len(d["values"])}))


if __name__ == "__main__":
    main()
