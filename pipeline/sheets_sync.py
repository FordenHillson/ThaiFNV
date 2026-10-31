#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sheets_sync.py — ดึง/สำรอง CSV จาก Google Sheets ของ ThaiFNV

ชีตหลัก:
  https://docs.google.com/spreadsheets/d/1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE

Usage:
  # ดึงทุกแท็บที่รู้จัก (หรือที่ระบุ) → extracted/sheets/from_google/
  python sheets_sync.py pull
  python sheets_sync.py pull --tabs FNV_Messages,FNV_Names

  # ลิสต์แท็บ + gid จาก HTML (ต้องแชร์ลิงก์ได้)
  python sheets_sync.py list

  # เตรียมรายการไฟล์ที่จะอัปโหลด (ยังไม่มี API push — ใช้ File>Import ในชีต)
  python sheets_sync.py pending
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SHEETS_DIR = ROOT / "extracted" / "sheets"
FROM_GOOGLE = SHEETS_DIR / "from_google"
BACKUP_DIR = ROOT / "corpus" / "sheets_backup"

SHEET_ID = "1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"

# gid ที่รู้แล้ว (อัปเดตเมื่อมีแท็บใหม่ — หรือใช้ list)
KNOWN_GIDS: dict[str, int] = {
    "FNV_Messages": 161309527,
    "FNV_SystemStr": 1230611415,
    "FNV_Other": 1979608645,
    "FNV_BookDesc": 1302236600,
    "FNV_Notes": 100349961,
    "FNV_Quests": 1936231527,
    "FNV_Terminals": 1013726487,
    "FNV_Names": 1872342141,
    "FNV_TopicNames": 715319255,
    "FNV_Dialogue": 288509415,
}

# ลำดับนำเข้าที่แนะนำ (Messages มีแล้ว)
UPLOAD_ORDER = [
    "FNV_SystemStr",
    "FNV_ExeUI",
    "FNV_Other",
    "FNV_BookDesc",
    "FNV_Descs",
    "FNV_Notes",
    "FNV_Quests",
    "FNV_Terminals",
    "FNV_Names",
    "FNV_TopicNames",
    "FNV_Dialogue",
]


def export_csv(gid: int, dest: Path) -> int:
    url = f"{SHEET_URL}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "ThaiFNV-sheets_sync/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    # นับแถวข้อมูล (ไม่นับ header)
    text = data.decode("utf-8-sig", errors="replace")
    rows = max(0, text.count("\n") - (0 if text.endswith("\n") else 0))
    # rough: lines-1
    n = len(text.splitlines())
    return max(0, n - 1)


def discover_tabs() -> dict[str, int]:
    """พยายามอ่านชื่อแท็บ+gid จากหน้า htmlview/edit (ขึ้นกับสิทธิ์แชร์)."""
    found: dict[str, int] = dict(KNOWN_GIDS)
    for path in ("htmlview", f"edit?usp=sharing"):
        url = f"{SHEET_URL}/{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ThaiFNV-sheets_sync/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print("skip %s: %s" % (path, e))
            continue
        # รูปแบบที่พบบ่อยในหน้า Sheets
        for name, gid in re.findall(
            r'\["([^"]+)",\d+,\d+,\d+[^]]*?\].*?(\d{5,})', html
        ):
            if name.startswith("FNV_") or name in found:
                found[name] = int(gid)
        for m in re.finditer(
            r'name":"([^"]+)".{0,80}?gid":\s*"?(-?\d+)', html
        ):
            found[m.group(1)] = int(m.group(2))
        for m in re.finditer(r'\[null,"(FNV_[^"]+)",[^\]]*?,-?\d+,-?\d+,-?\d+,(\d+)\]', html):
            found[m.group(1)] = int(m.group(2))
    return found


def cmd_list(_args: argparse.Namespace) -> None:
    tabs = discover_tabs()
    print("Sheet: %s" % SHEET_URL)
    if not tabs:
        print("(ไม่พบแท็บ — ใช้ KNOWN_GIDS)")
        tabs = dict(KNOWN_GIDS)
    for name, gid in sorted(tabs.items(), key=lambda x: x[0]):
        print("  %-20s gid=%s" % (name, gid))
    meta = FROM_GOOGLE / "_tabs.json"
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps(tabs, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote %s" % meta)


def cmd_pull(args: argparse.Namespace) -> None:
    tabs = discover_tabs()
    tabs.update(KNOWN_GIDS)
    if args.tabs:
        want = [t.strip() for t in args.tabs.split(",") if t.strip()]
    else:
        want = sorted(tabs.keys())
    FROM_GOOGLE.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    for name in want:
        gid = tabs.get(name)
        if gid is None:
            print("SKIP %s (ไม่มี gid — รัน list หลังสร้างแท็บ หรือใส่ใน KNOWN_GIDS)" % name)
            continue
        dest = FROM_GOOGLE / f"{name}.csv"
        n = export_csv(gid, dest)
        bak = BACKUP_DIR / f"{name}_{today}.csv"
        bak.write_bytes(dest.read_bytes())
        print("OK  %-20s rows≈%d → %s" % (name, n, dest))


def cmd_pending(_args: argparse.Namespace) -> None:
    """หมวดใน extracted/sheets ที่ยังไม่มีใน from_google (ยกเว้น Messages ถ้ามีแล้ว)."""
    existing = {p.stem for p in FROM_GOOGLE.glob("FNV_*.csv")}
    print("อัปโหลดเข้าชีต (File → Import → Insert new sheet) ตามลำดับ:\n")
    for name in UPLOAD_ORDER:
        src = SHEETS_DIR / f"{name}.csv"
        if not src.exists():
            print("  MISSING %s" % src)
            continue
        with src.open(encoding="utf-8-sig", newline="") as f:
            rows = sum(1 for _ in csv.DictReader(f))
        mark = "มีใน from_google แล้ว" if name in existing else "รออัปโหลด"
        print("  %-20s %6d แถว  [%s]" % (name, rows, mark))
        print("           %s" % src)
    print("\nชีต: %s" % SHEET_URL)
    print("หลัง Import ตั้งชื่อแท็บให้ตรงชื่อไฟล์ (เช่น FNV_Names)")
    print("แล้วรัน: python pipeline/sheets_sync.py list")
    print("         python pipeline/sheets_sync.py pull")


def main() -> None:
    ap = argparse.ArgumentParser(description="ThaiFNV Google Sheets sync")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="ลิสต์แท็บ + gid")
    p_list.set_defaults(func=cmd_list)

    p_pull = sub.add_parser("pull", help="ดึง CSV จากชีต")
    p_pull.add_argument("--tabs", default="", help="คอมมา: FNV_Names,FNV_Quests")
    p_pull.set_defaults(func=cmd_pull)

    p_pending = sub.add_parser("pending", help="ไฟล์ที่ยังต้อง Import ขึ้นชีต")
    p_pending.set_defaults(func=cmd_pending)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
