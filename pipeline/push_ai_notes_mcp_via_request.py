#!/usr/bin/env python3
"""Push push/_mcp_args/*.json via Cursor REST MCP (needs valid x-cursor-auth)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib import error, request

MCP_URL = "https://api.cursor.com/rest-mcp/google-sheets/mcp"
ARGS_DIR = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_ai_notes" / "push" / "_mcp_args"
SKIP = {"F0002.json", "F0042.json"}


def auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    for key in (
        "CURSOR_AUTH_TOKEN",
        "CURSOR_SESSION_TOKEN",
        "CURSOR_API_KEY",
        "CURSOR_REQUEST_ID",
    ):
        val = os.environ.get(key)
        if val:
            headers["x-cursor-auth"] = val
            break
    return headers


def mcp_write(args: dict, headers: dict[str, str], retries: int = 3) -> dict:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "write_range", "arguments": args},
        }
    ).encode()
    for attempt in range(retries + 1):
        req = request.Request(MCP_URL, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=180) as res:
                return json.loads(res.read().decode())
        except error.HTTPError as e:
            text = e.read().decode()
            if e.code == 429 and attempt < retries:
                print("429 wait 60s", args.get("cells"), file=sys.stderr)
                time.sleep(60)
                continue
            raise RuntimeError(f"HTTP {e.code}: {text[:400]}") from e
    raise RuntimeError("unreachable")


def main() -> None:
    headers = auth_headers()
    if "x-cursor-auth" not in headers:
        print("no x-cursor-auth in env", file=sys.stderr)
        sys.exit(2)
    log: list[dict] = []
    rows = 0
    for path in sorted(ARGS_DIR.glob("F*.json")):
        if path.name in SKIP:
            continue
        args = json.loads(path.read_text(encoding="utf-8"))
        try:
            out = mcp_write(args, headers)
            n = len(args["values"])
            rows += n
            log.append({"file": path.name, "cells": args["cells"], "rows": n, "ok": True, "out": out})
            print("OK", path.name, args["cells"], n)
        except Exception as e:
            log.append({"file": path.name, "cells": args.get("cells"), "ok": False, "error": str(e)})
            print("FAIL", path.name, e, file=sys.stderr)
    summary = {
        "filesWritten": sum(1 for x in log if x.get("ok")),
        "totalRows": rows,
        "log": log,
    }
    out_path = ARGS_DIR.parent / "_mcp_push_log.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FILES_WRITTEN", summary["filesWritten"], "ROWS", rows)
    sys.exit(0 if not any(not x.get("ok") for x in log) else 1)


if __name__ == "__main__":
    main()
