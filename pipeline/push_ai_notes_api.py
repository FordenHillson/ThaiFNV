#!/usr/bin/env python3
"""Push FNV_Notes AI translation batches to Google Sheets (Sheets API v4)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN = r"C:\Users\saetanpee\AppData\Roaming\ThaiW3Setup\google_token.json"
PUSH = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_ai_notes" / "push"
ARGS_DIR = PUSH / "_mcp_args"
PROGRESS = PUSH / "_push_progress.json"
SPREADSHEET = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"


def load_batch(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    raw = json.loads(text)
    return {
        "spreadsheetId": SPREADSHEET,
        "sheet": raw["sheet"],
        "cells": raw["cells"],
        "values": raw["values"],
    }


def load_mcp_args(name: str) -> dict:
    return json.loads((ARGS_DIR / name).read_text(encoding="utf-8"))


def push_one(service, d: dict, retries: int = 5) -> dict:
    rng = f"{d['sheet']}!{d['cells']}"
    for attempt in range(retries + 1):
        try:
            return (
                service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=d["spreadsheetId"],
                    range=rng,
                    valueInputOption="RAW",
                    body={"values": d["values"]},
                )
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 429 and attempt < retries:
                print("429 rate limit, waiting 60s...", d["cells"], file=sys.stderr)
                time.sleep(60)
                continue
            raise
    raise RuntimeError("unreachable")


def main() -> None:
    creds = Credentials.from_authorized_user_file(TOKEN)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    if PROGRESS.is_file():
        prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
        files = sorted(prog.get("pending") or [])
        loader = load_mcp_args
    else:
        files = sorted(p.name for p in PUSH.glob("F*.json"))
        loader = lambda name: load_batch(PUSH / name)  # noqa: E731
    log = {"ok": [], "fail": []}
    total_rows = 0
    for label in files:
        try:
            d = loader(label)
            resp = push_one(service, d)
            n = len(d["values"])
            total_rows += n
            log["ok"].append(
                {"file": label, "cells": d["cells"], "rows": n, "updatedRange": resp.get("updatedRange")}
            )
            print("OK", label, d["cells"], n, resp.get("updatedRange"))
            if PROGRESS.is_file():
                prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
                if label not in prog.setdefault("ok", []):
                    prog["ok"].append(label)
                prog["ok"] = sorted(prog["ok"])
                if label in prog.get("pending", []):
                    prog["pending"].remove(label)
                PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            log["fail"].append({"file": label, "error": str(e)})
            print("FAIL", label, e, file=sys.stderr)
            if PROGRESS.is_file():
                prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
                prog.setdefault("failures", []).append({"file": label, "error": str(e)})
                PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "filesWritten": len(log["ok"]),
        "totalRows": total_rows,
        "log": log,
    }
    out = PUSH / "_upload_api_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FILES_WRITTEN", len(log["ok"]), "TOTAL_ROWS", total_rows, "FAILURES", len(log["fail"]))
    sys.exit(1 if log["fail"] else 0)


if __name__ == "__main__":
    main()
