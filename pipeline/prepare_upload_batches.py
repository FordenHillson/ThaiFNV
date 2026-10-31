#!/usr/bin/env python3
"""Split upload_merged CSVs into JSON batches for Google Sheets write_range (≤10000 cells)."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path("extracted/sheets/upload_merged")
OUT = Path("extracted/sheets/_upload_batches")
FIELDS = ["ID", "ประเภท", "FormID", "EditorID", "EN", "TH", "สถานะ", "หมายเหตุ"]
# 8 cols → max 1250 rows/batch; keep headroom
BATCH = 1000


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    manifest = []
    for csv_path in sorted(ROOT.glob("FNV_*.csv")):
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        values_all = [[str(r.get(k) or "") for k in FIELDS] for r in rows]

        batches: list[dict] = []
        # Batch 0: header + first (BATCH-1) data rows → sheet rows 1..BATCH
        first = values_all[: BATCH - 1]
        batches.append({"start_row": 1, "values": [FIELDS] + first})

        idx = BATCH - 1
        row_num = BATCH + 1
        while idx < len(values_all):
            chunk = values_all[idx : idx + BATCH]
            batches.append({"start_row": row_num, "values": chunk})
            idx += BATCH
            row_num += BATCH

        tab_dir = OUT / csv_path.stem
        tab_dir.mkdir()
        for i, b in enumerate(batches):
            payload = {
                "sheet": csv_path.stem,
                "cells": f"A{b['start_row']}",
                "values": b["values"],
                "n_rows": len(b["values"]),
                "n_cells": len(b["values"]) * 8,
            }
            (tab_dir / f"{i:03d}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )

        manifest.append(
            {
                "tab": csv_path.stem,
                "rows": len(rows),
                "batches": len(batches),
                "need_rows": len(rows) + 1,
            }
        )
        print(f"{csv_path.stem:18} data={len(rows):6} batches={len(batches):3}")

    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("done", OUT)


if __name__ == "__main__":
    main()
