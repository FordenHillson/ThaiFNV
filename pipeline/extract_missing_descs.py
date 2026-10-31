#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_missing_descs.py — ดึง DESC ที่ตกหล่น (AVIF/PERK/...) จาก FalloutNV.esm
เขียน extracted/sheets/FNV_Descs.csv สำหรับอัปขึ้น Sheet

Usage:
  python extract_missing_descs.py --esm \"D:\\...\\FalloutNV.esm\"
"""
from __future__ import annotations

import argparse
import csv
import struct
import sys
import zlib
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "extracted" / "sheets" / "FNV_Descs.csv"
FIELDS = ["ID", "ประเภท", "FormID", "EditorID", "EN", "TH", "สถานะ", "หมายเหตุ"]

TYPES = {b"AVIF", b"PERK", b"WEAP", b"ARMO", b"ALCH", b"SPEL", b"MISC", b"KEYM", b"AMMO"}
FLAG_COMPRESSED = 0x00040000


def decompress(payload: bytes) -> bytes | None:
    try:
        return zlib.decompress(payload)
    except zlib.error:
        pass
    try:
        return zlib.decompress(payload[4:])
    except zlib.error:
        return None


def walk(data: bytes, pos: int, end: int, rows: list):
    while pos + 4 <= end:
        tag = data[pos : pos + 4]
        if tag == b"GRUP":
            gsize = struct.unpack_from("<I", data, pos + 4)[0]
            if gsize < 24 or pos + gsize > end:
                break
            walk(data, pos + 24, pos + gsize, rows)
            pos += gsize
            continue
        if pos + 24 > end:
            break
        rsize = struct.unpack_from("<I", data, pos + 4)[0]
        flags = struct.unpack_from("<I", data, pos + 8)[0]
        formid = struct.unpack_from("<I", data, pos + 12)[0]
        pe = pos + 24 + rsize
        if pe > end:
            break
        if tag in TYPES:
            payload = data[pos + 24 : pe]
            if flags & FLAG_COMPRESSED:
                payload = decompress(payload) or b""
            edid = ""
            p = 0
            while p + 6 <= len(payload):
                st = payload[p : p + 4]
                ss = struct.unpack_from("<H", payload, p + 4)[0]
                body = payload[p + 6 : p + 6 + ss]
                if st == b"EDID":
                    edid = body.split(b"\x00", 1)[0].decode("ascii", "replace")
                elif st == b"DESC" and ss >= 1:
                    en = body.split(b"\x00", 1)[0].decode("cp1252", "replace")
                    if en.strip():
                        rows.append(
                            {
                                "ประเภท": f"{tag.decode('ascii')}:DESC",
                                "FormID": f"{formid:08X}",
                                "EditorID": edid,
                                "EN": en,
                                "TH": "",
                                "สถานะ": "",
                                "หมายเหตุ": "",
                            }
                        )
                p += 6 + ss
        pos = pe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--esm",
        default=r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\FalloutNV.esm",
    )
    args = ap.parse_args()
    data = Path(args.esm).read_bytes()
    tes4 = struct.unpack_from("<I", data, 4)[0]
    rows: list[dict] = []
    walk(data, 24 + tes4, len(data), rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            r = dict(r)
            r["ID"] = i
            w.writerow(r)
    print("wrote %s (%d rows)" % (OUT, len(rows)))
    by = {}
    for r in rows:
        t = r["ประเภท"].split(":")[0]
        by[t] = by.get(t, 0) + 1
    print("by type:", by)


if __name__ == "__main__":
    main()
