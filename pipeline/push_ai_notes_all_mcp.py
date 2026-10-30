#!/usr/bin/env python3
"""Load all push batch args; print one JSON object per line for agent MCP write_range."""
from __future__ import annotations

import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_ai_notes" / "push" / "_mcp_args"


def main() -> None:
    for name in sorted(f for f in os.listdir(BASE) if f.endswith(".json")):
        raw = json.loads((BASE / name).read_text(encoding="utf-8"))
        print(json.dumps({"file": name, **raw}, ensure_ascii=False))


if __name__ == "__main__":
    main()
