#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""รวม th_*.json ทั้งหมดลง CSV แล้วเตรียมไฟล์ push สำหรับ Sheets"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "extracted" / "sheets" / "from_google" / "FNV_Notes.csv"
AI = ROOT / "extracted" / "sheets" / "from_google" / "_ai_notes"
PUSH = AI / "push"
FIELDS = ["ID", "ประเภท", "FormID", "EditorID", "EN", "TH", "สถานะ", "หมายเหตุ"]


def main() -> None:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    by_row: dict[int, str] = {}
    files = sorted(AI.glob("th_*.json"))
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data["items"] if isinstance(data, dict) else data
        for it in items:
            by_row[int(it["row"])] = it["th"]
        print("loaded", path.name, len(items))

    for i, r in enumerate(rows):
        sr = i + 2
        if sr in by_row:
            r["TH"] = by_row[sr]
            r["สถานะ"] = "ai"

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})

    ai_count = sum(1 for r in rows if (r.get("สถานะ") or "") == "ai")
    print("CSV ai rows:", ai_count, "/", len(rows), "from", len(by_row), "translated")

    PUSH.mkdir(parents=True, exist_ok=True)
    for p in PUSH.glob("*.json"):
        p.unlink()

    # contiguous ai blocks
    pairs = [
        (i + 2, [rows[i].get("TH") or "", "ai"])
        for i in range(len(rows))
        if (rows[i].get("สถานะ") or "") == "ai"
    ]
    chunk = 40
    idx = 0
    nbatch = 0
    while idx < len(pairs):
        start = pairs[idx][0]
        block = [pairs[idx][1]]
        j = idx + 1
        while (
            j < len(pairs)
            and pairs[j][0] == pairs[j - 1][0] + 1
            and len(block) < chunk
        ):
            block.append(pairs[j][1])
            j += 1
        meta = {"sheet": "FNV_Notes", "cells": f"F{start}", "values": block}
        (PUSH / f"F{start:04d}.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        nbatch += 1
        idx = j
    print("push batches:", nbatch)


if __name__ == "__main__":
    main()
