#!/usr/bin/env python3
"""Print ordered chunk filenames for MCP write_range (one per line)."""
from __future__ import annotations

from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"


def main() -> None:
    for p in sorted(BASE.glob("_mcp_chunk_*.json")):
        print(p.name)
    print("FNV_Notes_F967_G1020.json")


if __name__ == "__main__":
    main()
