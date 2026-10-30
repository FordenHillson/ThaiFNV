#!/usr/bin/env python3
import json
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN = r"C:\Users\saetanpee\AppData\Roaming\ThaiW3Setup\google_token.json"
SPREADSHEET = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"
PUSH = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_ai_notes" / "push"
SKIP = {"F0002.json"}  # already pushed via MCP this session


def main() -> None:
    creds = Credentials.from_authorized_user_file(TOKEN)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        Path(TOKEN).write_text(creds.to_json(), encoding="utf-8")
        print("refreshed token")
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    log = []
    for path in sorted(PUSH.glob("F*.json")):
        if path.name in SKIP:
            continue
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        rng = f"{raw['sheet']}!{raw['cells']}"
        for attempt in range(4):
            try:
                resp = (
                    service.spreadsheets()
                    .values()
                    .update(
                        spreadsheetId=SPREADSHEET,
                        range=rng,
                        valueInputOption="RAW",
                        body={"values": raw["values"]},
                    )
                    .execute()
                )
                log.append(
                    {
                        "file": path.name,
                        "cells": raw["cells"],
                        "rows": len(raw["values"]),
                        "updatedRange": resp.get("updatedRange"),
                        "ok": True,
                    }
                )
                print("OK", path.name, raw["cells"], len(raw["values"]))
                break
            except HttpError as e:
                if e.resp.status == 429 and attempt < 3:
                    print("429 wait 60s", path.name)
                    time.sleep(60)
                    continue
                log.append({"file": path.name, "ok": False, "error": str(e)})
                print("FAIL", path.name, e)
                break
            except Exception as e:
                log.append({"file": path.name, "ok": False, "error": str(e)})
                print("FAIL", path.name, e)
                break
    summary = {
        "filesWritten": sum(1 for x in log if x.get("ok")),
        "failures": [x for x in log if not x.get("ok")],
        "log": log,
    }
    (PUSH / "_api_push_log.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("FILES_WRITTEN", summary["filesWritten"], "FAIL", len(summary["failures"]))


if __name__ == "__main__":
    main()
