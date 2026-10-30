#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = r"C:\Users\saetanpee\AppData\Roaming\ThaiW3Setup\google_token.json"
BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"
SPREADSHEET = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"


def main() -> None:
    creds = Credentials.from_authorized_user_file(TOKEN)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    total = 0
    for p in sorted(BASE.glob("_mcp_chunk_*.json")):
        d = json.load(p.open(encoding="utf-8"))
        rng = f"{d['sheet']}!{d['cells']}"
        resp = (
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
        n = len(d["values"])
        total += n
        print(p.name, resp.get("updatedRange"), n)
    # batch 8 F967
    p8 = BASE / "FNV_Notes_F967_G1020.json"
    if p8.exists():
        d = json.load(p8.open(encoding="utf-8"))
        body = {
            "spreadsheetId": SPREADSHEET,
            "sheet": d["sheet"],
            "cells": d["cells"],
            "values": d["values"],
        }
        rng = f"{body['sheet']}!{body['cells']}"
        resp = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=body["spreadsheetId"],
                range=rng,
                valueInputOption="RAW",
                body={"values": body["values"]},
            )
            .execute()
        )
        n = len(body["values"])
        total += n
        print(p8.name, resp.get("updatedRange"), n)
    print("TOTAL_ROWS", total)


if __name__ == "__main__":
    main()
