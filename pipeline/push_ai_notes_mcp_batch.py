#!/usr/bin/env python3
"""Load one _mcp_args JSON and print write_range args (stdout) for agent MCP."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ARGS_DIR = (
    Path(__file__).resolve().parents[1]
    / "extracted"
    / "sheets"
    / "from_google"
    / "_ai_notes"
    / "push"
    / "_mcp_args"
)


def main() -> None:
    name = sys.argv[1]
    path = ARGS_DIR / name
    sys.stdout.write(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
