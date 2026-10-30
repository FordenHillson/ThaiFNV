#!/usr/bin/env python3
"""Update _push_progress.json after a successful MCP write_range batch."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PUSH = (
    Path(__file__).resolve().parents[1]
    / "extracted"
    / "sheets"
    / "from_google"
    / "_ai_notes"
    / "push"
)
PROGRESS = PUSH / "_push_progress.json"
ARGS_DIR = PUSH / "_mcp_args"


def mark_ok(filename: str) -> None:
    prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
    if filename not in prog.setdefault("ok", []):
        prog["ok"].append(filename)
    prog["ok"] = sorted(prog["ok"])
    if filename in prog.get("pending", []):
        prog["pending"].remove(filename)
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_fail(filename: str, error: str) -> None:
    prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
    prog.setdefault("failures", []).append({"file": filename, "error": error})
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")


def load_args(filename: str) -> dict:
    return json.loads((ARGS_DIR / filename).read_text(encoding="utf-8"))


def summary() -> dict:
    prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
    ok = prog.get("ok", [])
    rows = 0
    for name in ok:
        if (ARGS_DIR / name).is_file():
            rows += len(load_args(name)["values"])
    return {
        "filesWritten": len(ok),
        "totalRows": rows,
        "pending": prog.get("pending", []),
        "failures": prog.get("failures", []),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps(summary(), ensure_ascii=False))
        return
    cmd = sys.argv[1]
    if cmd == "ok" and len(sys.argv) >= 3:
        mark_ok(sys.argv[2])
    elif cmd == "fail" and len(sys.argv) >= 4:
        mark_fail(sys.argv[2], sys.argv[3])
    elif cmd == "args" and len(sys.argv) >= 3:
        print(json.dumps(load_args(sys.argv[2]), ensure_ascii=False))
    elif cmd == "pending":
        prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
        for f in prog.get("pending", []):
            print(f)
    else:
        print(json.dumps(summary(), ensure_ascii=False))


if __name__ == "__main__":
    main()
