#!/usr/bin/env python3
"""Upload for_sheet_upload/*.csv into ThaiFNV Google Sheet (create tabs, resize, clear, write)."""
from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN = r"C:\Users\saetanpee\AppData\Roaming\ThaiW3Setup\google_token.json"
SPREADSHEET = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"
# Default: merged extract+TH. Override with env THAIFNV_SHEET_SRC.
SRC = Path(
    os.environ.get(
        "THAIFNV_SHEET_SRC",
        str(Path(__file__).resolve().parents[1] / "extracted" / "sheets" / "upload_merged"),
    )
)
COLS = 8
# ~8k cells/request keeps MCP-era habit; Sheets API allows more — still chunk for reliability
ROWS_PER_CHUNK = 1000
CLEAR_PAD = 50  # clear a few extra empty rows after data


def load_csv(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < COLS:
                row = row + [""] * (COLS - len(row))
            elif len(row) > COLS:
                row = row[:COLS]
            rows.append(row)
    return rows


def with_retry(fn, *, label: str, retries: int = 6):
    for attempt in range(retries + 1):
        try:
            return fn()
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status in (429, 500, 503) and attempt < retries:
                wait = 30 if status == 429 else 5 * (attempt + 1)
                print(f"  {label}: HTTP {status}, wait {wait}s…", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


def ensure_tabs(service, titles: list[str], existing: dict[str, dict]) -> dict[str, dict]:
    requests = []
    for title in titles:
        if title in existing:
            continue
        requests.append(
            {
                "addSheet": {
                    "properties": {
                        "title": title,
                        "gridProperties": {"rowCount": 2000, "columnCount": COLS},
                    }
                }
            }
        )
    if requests:
        resp = with_retry(
            lambda: service.spreadsheets()
            .batchUpdate(spreadsheetId=SPREADSHEET, body={"requests": requests})
            .execute(),
            label="addSheet",
        )
        for reply in resp.get("replies", []):
            props = reply["addSheet"]["properties"]
            existing[props["title"]] = props
            print(f"  + created tab {props['title']} sheetId={props['sheetId']}")
    return existing


def resize_sheet(service, sheet_id: int, title: str, row_count: int, col_count: int = COLS) -> None:
    need = row_count + CLEAR_PAD
    with_retry(
        lambda: service.spreadsheets()
        .batchUpdate(
            spreadsheetId=SPREADSHEET,
            body={
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": sheet_id,
                                "gridProperties": {
                                    "rowCount": need,
                                    "columnCount": max(col_count, COLS),
                                },
                            },
                            "fields": "gridProperties.rowCount,gridProperties.columnCount",
                        }
                    }
                ]
            },
        )
        .execute(),
        label=f"resize {title}",
    )
    print(f"  resized {title} -> {need} rows x {max(col_count, COLS)} cols")


def clear_and_write(service, title: str, values: list[list[str]], old_rows: int) -> None:
    clear_end = max(old_rows, len(values)) + CLEAR_PAD
    clear_range = f"{title}!A1:H{clear_end}"
    with_retry(
        lambda: service.spreadsheets()
        .values()
        .clear(spreadsheetId=SPREADSHEET, range=clear_range)
        .execute(),
        label=f"clear {title}",
    )
    total = 0
    for i in range(0, len(values), ROWS_PER_CHUNK):
        chunk = values[i : i + ROWS_PER_CHUNK]
        start = i + 1
        end = i + len(chunk)
        rng = f"{title}!A{start}:H{end}"
        with_retry(
            lambda rng=rng, chunk=chunk: service.spreadsheets()
            .values()
            .update(
                spreadsheetId=SPREADSHEET,
                range=rng,
                valueInputOption="RAW",
                body={"values": chunk},
            )
            .execute(),
            label=f"write {title} {start}-{end}",
        )
        total += len(chunk)
        print(f"  wrote {title} {start}-{end} ({total}/{len(values)})")
        time.sleep(0.15)


def main() -> None:
    creds = Credentials.from_authorized_user_file(TOKEN)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    meta = (
        service.spreadsheets()
        .get(spreadsheetId=SPREADSHEET, fields="sheets.properties")
        .execute()
    )
    existing = {s["properties"]["title"]: s["properties"] for s in meta["sheets"]}

    csvs = sorted(SRC.glob("FNV_*.csv"))
    titles = [p.stem for p in csvs]
    print("tabs needed:", titles)
    existing = ensure_tabs(service, titles, existing)

    # refresh after creates
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=SPREADSHEET, fields="sheets.properties")
        .execute()
    )
    existing = {s["properties"]["title"]: s["properties"] for s in meta["sheets"]}

    # Prefer smaller tabs first so partial progress is useful if interrupted
    order = [
        "FNV_BookDesc",
        "FNV_Other",
        "FNV_SystemStr",
        "FNV_Descs",
        "FNV_ExeUI",
        "FNV_Quests",
        "FNV_Notes",
        "FNV_Messages",
        "FNV_Terminals",
        "FNV_Names",
        "FNV_TopicNames",
        "FNV_Dialogue",
    ]
    by_stem = {p.stem: p for p in csvs}
    for title in order:
        path = by_stem.get(title)
        if not path:
            continue
        props = existing[title]
        values = load_csv(path)
        old_rows = props.get("gridProperties", {}).get("rowCount", 1000)
        print(f"\n=== {title}: {len(values)} rows (grid was {old_rows}) ===")
        if len(values) + CLEAR_PAD > old_rows or props.get("gridProperties", {}).get("columnCount", 0) < COLS:
            resize_sheet(service, props["sheetId"], title, len(values), COLS)
        clear_and_write(service, title, values, old_rows)
        # freeze header
        with_retry(
            lambda sid=props["sheetId"]: service.spreadsheets()
            .batchUpdate(
                spreadsheetId=SPREADSHEET,
                body={
                    "requests": [
                        {
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": sid,
                                    "gridProperties": {"frozenRowCount": 1},
                                },
                                "fields": "gridProperties.frozenRowCount",
                            }
                        }
                    ]
                },
            )
            .execute(),
            label=f"freeze {title}",
        )

    print("\nDONE")


if __name__ == "__main__":
    main()
