#!/usr/bin/env python3
"""Queue one MCP write_range payload at a time for FNV_Notes invoke files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else r"C:\Users\saetanpee\AppData\Local\Cursor\AgentStores\cursor_agent_stores\f277bb1f-18c1-446d-97ec-8f94cb76d6fd\files\mcp_invoke"
)
PROGRESS = INVOKE.parent / "_mcp_push_progress.json"
ALSO = [
    INVOKE.parent / "chunk_2_invoke.json",
    INVOKE.parent / "chunk_342_invoke.json",
    INVOKE.parent / "chunk_682_invoke.json",
]


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {"ok": [], "fail": []}


def save_progress(prog: dict) -> None:
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")


def queue() -> list[Path]:
    files = sorted(INVOKE.glob("F*_invoke.json"))
    return files


def main() -> None:
    cmd = sys.argv[2] if len(sys.argv) > 2 else "next"
    prog = load_progress()
    done = set(prog.get("ok", []))
    if cmd == "mark":
        name = sys.argv[3]
        status = sys.argv[4]
        if status == "ok":
            if name not in prog["ok"]:
                prog["ok"].append(name)
        else:
            prog.setdefault("fail", []).append(name)
        save_progress(prog)
        print("MARKED", name, status)
        return
    if cmd == "status":
        print(json.dumps(prog, ensure_ascii=False))
        return
    for p in queue():
        if p.name in done:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        row = {"file": p.name, "args": d}
        sys.stdout.write(json.dumps(row, ensure_ascii=False))
        return
    print("ALL_DONE", len(done))


if __name__ == "__main__":
    main()
