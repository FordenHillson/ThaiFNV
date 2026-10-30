#!/usr/bin/env python3
"""
Push all FNV_Notes _mcp_args batches via Cursor Google Sheets MCP REST.
Requires valid x-cursor-auth (only works inside Cursor agent shell with session token).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MCP_DIR = (
    Path(__file__).resolve().parents[1]
    / "extracted"
    / "sheets"
    / "from_google"
    / "_ai_notes"
    / "push"
    / "_mcp_args"
)
OUT = MCP_DIR.parent / "_upload_mcp_agent_summary.json"
MCP_URL = "https://api.cursor.com/rest-mcp/google-sheets/mcp"


def auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    for key in (
        "CURSOR_SESSION_TOKEN",
        "CURSOR_AGENT_AUTH",
        "CURSOR_AUTH_TOKEN",
        "CURSOR_REQUEST_ID",
    ):
        if os.environ.get(key):
            headers["x-cursor-auth"] = os.environ[key]
            break
    if os.environ.get("CURSOR_REQUEST_ID"):
        headers["x-cursor-request-id"] = os.environ["CURSOR_REQUEST_ID"]
    if os.environ.get("CURSOR_CONVERSATION_ID"):
        headers["x-cursor-conversation-id"] = os.environ["CURSOR_CONVERSATION_ID"]
    return headers


def mcp_write(args: dict, retries: int = 5) -> dict:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "write_range", "arguments": args},
        }
    ).encode("utf-8")
    headers = auth_headers()
    for attempt in range(retries + 1):
        req = urllib.request.Request(MCP_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            if resp.status == 429 and attempt < retries:
                print("429 wait 60s", args.get("cells"), file=sys.stderr)
                time.sleep(60)
                continue
            return json.loads(text)
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < retries:
                print("429 wait 60s", args.get("cells"), file=sys.stderr)
                time.sleep(60)
                continue
            raise RuntimeError(f"HTTP {e.code}: {text[:500]}") from e
    raise RuntimeError("max retries")


def main() -> None:
    skip = set((sys.argv[1] or "").split(",")) if len(sys.argv) > 1 else set()
    log = {"ok": [], "fail": []}
    total_rows = 0
    for path in sorted(MCP_DIR.glob("F*.json")):
        if path.name in skip:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        args = {
            "spreadsheetId": data["spreadsheetId"],
            "sheet": data["sheet"],
            "cells": data["cells"],
            "values": data["values"],
        }
        try:
            out = mcp_write(args)
            n = len(args["values"])
            total_rows += n
            log["ok"].append({"file": path.name, "cells": args["cells"], "rows": n, "out": out})
            print("OK", path.name, args["cells"], n)
            time.sleep(0.25)
        except Exception as e:
            log["fail"].append({"file": path.name, "cells": args["cells"], "error": str(e)})
            print("FAIL", path.name, e, file=sys.stderr)
    summary = {"filesWritten": len(log["ok"]), "totalRows": total_rows, "log": log}
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FILES_WRITTEN", len(log["ok"]), "TOTAL_ROWS", total_rows, "FAILURES", len(log["fail"]))
    sys.exit(1 if log["fail"] else 0)


if __name__ == "__main__":
    main()
