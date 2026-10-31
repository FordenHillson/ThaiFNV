#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_categories.py — แบ่ง CSV extract (v1) เป็นไฟล์หมวด พร้อมคอลัมน์สำหรับ Google Sheets

คอลัมน์ผลลัพธ์: ID | ประเภท | FormID | EditorID | EN | TH | สถานะ | หมายเหตุ
- ID = running number เฉพาะภายในไฟล์ (ใช้อ้างอิงตอน import กลับ)
- สถานะ: ว่าง = ยังไม่แปล (MT seed จะเติม TH + ตั้งสถานะเป็น mt)

หมวด (category):
  Dialogue    INFO NAM1 (บทสนทนา)
  TopicNames  DIAL FULL (ชื่อ topic = ตัวเลือกบทพูด)
  Names       FULL ของ record อื่น ๆ (ไอเทม/NPC/สถานที่/perk)
  Messages    MESG ITXT/DESC (ข้อความเมนู/เตือน)
  Terminals   TERM DESC/ITXT/RNAM
  Quests      QUST NNAM
  Notes       NOTE TNAM/FULL
  BookDesc    BOOK DESC
  Descs       DESC ของ AVIF/PERK/WEAP/ARMO/... (คำอธิบาย Pip-Boy)
  SystemStr   GMST DATA (ข้อความระบบ s*)

Usage:
  python make_categories.py ..\\extracted\\FalloutNV_extract_v1.csv --out-dir ..\\extracted\\sheets
"""
from __future__ import annotations
import argparse
import csv
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FIELDS = ["ID", "ประเภท", "FormID", "EditorID", "EN", "TH", "สถานะ", "หมายเหตุ"]


def categorize(r):
    rt, sub = r["record_type"], r["subrecord"]
    if rt == "INFO":
        return "Dialogue"
    if rt == "DIAL":
        return "TopicNames"
    if rt == "TERM":
        return "Terminals"
    if rt == "QUST":
        return "Quests"
    if rt == "BOOK":
        return "BookDesc"
    if rt == "NOTE":
        return "Notes"
    if rt == "MESG":
        return "Messages"
    if rt == "GMST" and r["edid"].startswith("s"):
        return "SystemStr"
    if sub == "DESC" and rt in (
        "AVIF", "PERK", "WEAP", "ARMO", "ALCH", "SPEL", "MISC", "KEYM", "AMMO",
    ):
        return "Descs"
    if sub == "FULL":
        return "Names"
    return "Other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out-dir", default="sheets")
    args = ap.parse_args()

    with open(args.src, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    buckets = {}
    for r in rows:
        buckets.setdefault(categorize(r), []).append(r)

    os.makedirs(args.out_dir, exist_ok=True)
    for cat, items in sorted(buckets.items()):
        path = os.path.join(args.out_dir, f"FNV_{cat}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for i, r in enumerate(items, 1):
                w.writerow({
                    "ID": i,
                    "ประเภท": f"{r['record_type']}:{r['subrecord']}",
                    "FormID": r["formid"],
                    "EditorID": r["edid"],
                    "EN": r["en"],
                    "TH": "",
                    "สถานะ": "",
                    "หมายเหตุ": "",
                })
        print("%-12s %6d rows -> %s" % (cat, len(items), path))
    print("total: %d" % len(rows))


if __name__ == "__main__":
    main()
