#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_gaps_for_sheets.py — extract ข้อความที่เคยตกหล่น + เตรียม CSV อัป Sheet

ทำอะไร:
  1) extract ใหม่จาก FalloutNV.esm (แก้บั๊ก \\r\\n / INFO RNAM / NEXT size0)
  2) แบ่งหมวด → extracted/sheets/FNV_*.csv
  3) ดึง UI จาก FalloutNV.exe → FNV_ExeUI.csv
  4) สรุปแถวใหม่เทียบรอบก่อน (ถ้ามี) → extracted/sheets/pending_upload/

Usage:
  python extract_gaps_for_sheets.py
"""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "pipeline"
SHEETS = ROOT / "extracted" / "sheets"
PENDING = SHEETS / "pending_upload"
ESM = Path(r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\FalloutNV.esm")
EXTRACT_OUT = ROOT / "extracted" / "FalloutNV_extract_v2.csv"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(PIPE))


def count_csv(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def main() -> None:
    py = sys.executable
    PENDING.mkdir(parents=True, exist_ok=True)

    # backup sheets รอบก่อน (ถ้ายังไม่มี snapshot)
    snap = SHEETS / "_prev_snapshot"
    if not snap.exists():
        snap.mkdir(parents=True, exist_ok=True)
        for p in SHEETS.glob("FNV_*.csv"):
            shutil.copy2(p, snap / p.name)
        print("snapshot previous sheets → %s" % snap)

    run([py, "fnv_esm.py", str(ESM), "--out", str(EXTRACT_OUT)])
    run([py, "make_categories.py", str(EXTRACT_OUT), "--out-dir", str(SHEETS)])
    run([py, "extract_exe_ui.py"])
    run([py, "extract_missing_descs.py"])  # ซ้ำกับ Descs จาก categories ก็ได้ — ยืนยัน AVIF/PERK

    # คัดลอกหมวดสำคัญไป pending_upload + สรุป diff
    summary = []
    upload_tabs = [
        "FNV_Descs",
        "FNV_ExeUI",
        "FNV_Messages",  # Help DESC ที่เคยหายจะโผล่ที่นี่
        "FNV_Dialogue",  # RNAM เพิ่ม
        "FNV_Names",
        "FNV_SystemStr",
        "FNV_TopicNames",
        "FNV_Notes",
        "FNV_Quests",
        "FNV_Terminals",
        "FNV_BookDesc",
        "FNV_Other",
    ]
    print("\n== pending upload ==")
    for name in upload_tabs:
        src = SHEETS / f"{name}.csv"
        if not src.exists():
            print("MISSING %s" % name)
            continue
        dest = PENDING / f"{name}.csv"
        shutil.copy2(src, dest)
        n = count_csv(src)
        prev = count_csv(snap / f"{name}.csv") if (snap / f"{name}.csv").exists() else None
        delta = "" if prev is None else (" %+d" % (n - prev))
        line = "%-18s %6d rows%s" % (name, n, delta)
        print(line)
        summary.append(line)

    # ไฮไลต์ Help DESC
    help_desc = 0
    msg = SHEETS / "FNV_Messages.csv"
    if msg.exists():
        with msg.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("EditorID") or "").startswith("Help") and (
                    r.get("ประเภท") or ""
                ).endswith("DESC"):
                    help_desc += 1
    print("Help*:DESC rows now:", help_desc)

    # RNAM count
    dial = SHEETS / "FNV_Dialogue.csv"
    rnam = 0
    if dial.exists():
        with dial.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("ประเภท") or "") == "INFO:RNAM":
                    rnam += 1
    print("INFO:RNAM rows:", rnam)

    readme = PENDING / "README.txt"
    readme.write_text(
        "\n".join(
            [
                "ThaiFNV — CSV พร้อม Import ขึ้น Google Sheet",
                "สร้างจาก extract_gaps_for_sheets.py",
                "",
                "วิธีอัป:",
                "  1) เปิดชีต ThaiFNV",
                "  2) File → Import → Insert new sheet (หรือแทนที่แท็บเดิมที่ตรงชื่อ)",
                "  3) ตั้งชื่อแท็บให้ตรงชื่อไฟล์ (เช่น FNV_ExeUI, FNV_Descs)",
                "",
                "หมวดใหม่ที่สำคัญ:",
                "  FNV_ExeUI  = ข้อความ UI จาก FalloutNV.exe (เมนู/ตั้งค่า/Pip-Boy/Companion)",
                "  FNV_Descs = คำอธิบาย AVIF/PERK (SPECIAL + Skills + Perks)",
                "  FNV_Messages = รวม Help DESC ที่เคยตกหล่นเพราะ \\r\\n",
                "  FNV_Dialogue = เพิ่ม INFO:RNAM (ตัวเลือกบทพูดบางรายการ)",
                "",
                "สรุปจำนวน:",
                *summary,
                "",
                "Help*:DESC = %d" % help_desc,
                "INFO:RNAM  = %d" % rnam,
            ]
        ),
        encoding="utf-8",
    )
    print("wrote %s" % readme)
    print("done → %s" % PENDING)


if __name__ == "__main__":
    main()
