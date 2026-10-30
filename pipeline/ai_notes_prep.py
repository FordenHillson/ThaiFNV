#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""เตรียม/รวมชุดแปล AI สำหรับ FNV_Notes"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "extracted" / "sheets" / "from_google" / "FNV_Notes.csv"
OUT = ROOT / "extracted" / "sheets" / "from_google" / "_ai_notes"
FIELDS = ["ID", "ประเภท", "FormID", "EditorID", "EN", "TH", "สถานะ", "หมายเหตุ"]


def load_rows() -> list[dict]:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cmd_prep(chunk: int) -> None:
    rows = load_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    print("rows", len(rows))
    print(dict(Counter(r.get("ประเภท", "") for r in rows)))
    for p in OUT.glob("batch_*.json"):
        p.unlink()
    for bi in range(0, len(rows), chunk):
        batch = []
        for i in range(bi, min(bi + chunk, len(rows))):
            batch.append(
                {
                    "row": i + 2,
                    "type": rows[i].get("ประเภท", ""),
                    "editor": rows[i].get("EditorID", ""),
                    "en": rows[i].get("EN") or "",
                }
            )
        path = OUT / f"batch_{bi + 2:04d}.json"
        path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", path.name, len(batch))


def cmd_apply(translated: Path) -> None:
    """รวมไฟล์ผลแปล [{row, th}, ...] ลง CSV และเตรียม push batches"""
    rows = load_rows()
    items = json.loads(translated.read_text(encoding="utf-8"))
    if isinstance(items, dict) and "items" in items:
        items = items["items"]
    by_row = {int(x["row"]): x["th"] for x in items}
    for i, r in enumerate(rows):
        sheet_row = i + 2
        if sheet_row in by_row:
            r["TH"] = by_row[sheet_row]
            r["สถานะ"] = "ai"
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    # push batches of 40
    push = OUT / "push"
    push.mkdir(exist_ok=True)
    for p in push.glob("*.json"):
        p.unlink()
    filled = [
        (i + 2, [rows[i].get("TH") or "", rows[i].get("สถานะ") or ""])
        for i in range(len(rows))
        if (rows[i].get("สถานะ") or "") == "ai" and (rows[i].get("TH") or "").strip()
    ]
    chunk = 40
    idx = 0
    while idx < len(filled):
        start = filled[idx][0]
        block = [filled[idx][1]]
        j = idx + 1
        while (
            j < len(filled)
            and filled[j][0] == filled[j - 1][0] + 1
            and len(block) < chunk
        ):
            block.append(filled[j][1])
            j += 1
        meta = {"sheet": "FNV_Notes", "cells": f"F{start}", "values": block}
        (push / f"F{start:04d}.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        print("push", f"F{start}", len(block))
        idx = j
    print("applied", len(by_row), "→", CSV_PATH)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("prep")
    p1.add_argument("--chunk", type=int, default=40)
    p2 = sub.add_parser("apply")
    p2.add_argument("translated", type=Path)
    args = ap.parse_args()
    if args.cmd == "prep":
        cmd_prep(args.chunk)
    else:
        cmd_apply(args.translated)


if __name__ == "__main__":
    main()
