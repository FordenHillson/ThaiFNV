#!/usr/bin/env python3
"""Print write_range args JSON for one _mcp_args file (stdout only)."""
import json
import sys
from pathlib import Path

ARGS = (
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
    print(json.dumps(json.loads((ARGS / name).read_text(encoding="utf-8")), ensure_ascii=False))


if __name__ == "__main__":
    main()
