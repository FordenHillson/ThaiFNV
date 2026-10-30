#!/usr/bin/env python3
"""Emit write_range args JSON from a chunk file path."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"


def main() -> None:
    arg = Path(sys.argv[1])
    path = arg if arg.is_absolute() else BASE / arg
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    sys.stdout.write(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
