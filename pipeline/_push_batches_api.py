#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = r"C:\Users\saetanpee\AppData\Roaming\ThaiW3Setup\google_token.json"
BASE = Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "from_google" / "_push_batches"


def main() -> None:
    creds = Credentials.from_authorized_user_file(TOKEN)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    total_rows = 0
    for i in range(8):
        d = json.load((BASE / f"_mcp_out{i}.args.json").open(encoding="utf-8"))
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
        total_rows += n
        print(
            i,
            d["cells"],
            n,
            resp.get("updatedRange"),
            resp.get("updatedCells"),
        )
    print("TOTAL_ROWS", total_rows)


if __name__ == "__main__":
    main()
