#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
เตรียมชุดค่า F:G (TH, สถานะ) จาก CSV ที่แปลแล้ว
สำหรับอัปโหลดผ่าน Google Sheets MCP write_range (สูงสุด ~5000 แถว/ครั้ง)

Usage:
  python push_th_batches.py FNV_Notes
  python push_th_batches.py --all
  python push_th_batches.py FNV_Notes --only-new --since-row 167
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "extracted" / "sheets" / "from_google"
BATCH = OUT / "_push_batches"
FIELDS_TH = ("TH", "สถานะ")
QUEUE = [
    "FNV_Notes",
    "FNV_Quests",
    "FNV_Terminals",
    "FNV_Names",
    "FNV_TopicNames",
    "FNV_Dialogue",
]


def export_tab(name: str, chunk: int, since_row: int | None, only_filled: bool) -> list[Path]:
    src = OUT / f"{name}.csv"
    if not src.exists():
        print("MISSING", src)
        return []
    with src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    pairs: list[tuple[int, list[str]]] = []
    for i, r in enumerate(rows):
        sheet_row = i + 2  # header is row 1
        if since_row is not None and sheet_row < since_row:
            continue
        th = (r.get("TH") or "").strip()
        st = (r.get("สถานะ") or "").strip()
        if only_filled and not th:
            continue
        if not th and not st:
            continue
        pairs.append((sheet_row, [r.get("TH") or "", r.get("สถานะ") or ""]))

    if not pairs:
        print("%s: nothing to export" % name)
        return []

    BATCH.mkdir(parents=True, exist_ok=True)
    # รวมช่วงติดกันแล้วตัด chunk
    written: list[Path] = []
    idx = 0
    while idx < len(pairs):
        start_row = pairs[idx][0]
        block = [pairs[idx][1]]
        j = idx + 1
        while j < len(pairs) and pairs[j][0] == pairs[j - 1][0] + 1 and len(block) < chunk:
            block.append(pairs[j][1])
            j += 1
        end_row = start_row + len(block) - 1
        path = BATCH / f"{name}_F{start_row}_G{end_row}.json"
        meta = {
            "sheet": name,
            "cells": f"F{start_row}",
            "rows": len(block),
            "values": block,
        }
        path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        written.append(path)
        print("  wrote %s (%d rows)" % (path.name, len(block)))
        idx = j
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tabs", nargs="*", help="ชื่อแท็บ")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--chunk", type=int, default=400)
    ap.add_argument("--since-row", type=int, default=None)
    ap.add_argument("--only-filled", action="store_true", default=True)
    args = ap.parse_args()

    tabs = QUEUE if args.all else list(args.tabs)
    if not tabs:
        ap.error("ระบุแท็บ หรือ --all")

    total = 0
    for t in tabs:
        print("==", t)
        paths = export_tab(t, args.chunk, args.since_row, args.only_filled)
        total += len(paths)
    print("batches:", total)


if __name__ == "__main__":
    main()
