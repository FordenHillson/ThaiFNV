#!/usr/bin/env python3
"""Print one write_range args JSON from a chunk file (stdout)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    path = Path(sys.argv[1])
    sys.stdout.write(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
