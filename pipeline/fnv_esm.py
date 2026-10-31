#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fnv_esm.py — Extractor ข้อความเกม (prototype v1) ของ ThaiFNV

ระดับสังเกต (Scope v1):
  - อ่านไฟล์ .esm / .esp ของ FNV (ฟอแมท Gamebryo) แบบ conceptual walk ทุก record/subrecord
  - ดึงข้อความที่แปลได้เบื้องต้น: FULL (ชื่อ) + DESC (รายละเอียด) ของทุก record type
  - Map: record type + FormID + EDID + subrecord type + ข้อความ EN
  - สร้างไฟล์ CSV ที่เผยแพร่форматรับส่งออกให้ปิดรายงานและสิทธิ์ตัวแปล
  - พร้อมสถิติชุดข้อเสนรายงานต่อเราทุกขั้น:

  - ข้อเห็นข้อจำกัด (Scope v1 = ฝึก): DIAL/INFO (บทสนทนา) จะนับจากรายจ่า record ตอนสถิติ
    และเจาะเปราเชรงการแปลในตัวต่อไปเถอ (ต้องตัดรายให้แค่ตัวที่เป็น "text" อย่างบาสเชือก)

Usage:
  python fnv_esm.py "path\ปรา?FalloutNV.esm" --out "D:\backup\github\ThaiFNV\extracted\out.csv"

เขียนสร้างสำเร็จติดขั้นตอนที่ให้ pipeline? ปรับระยะเฟส 1 ของ plan.md
"""
from __future__ import annotations
import argparse
import collections
import csv
import struct
import sys
import zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Subrecord ที่เก็บข้อความ — ยืนยันจาก inspect_subs.py บน FalloutNV.esm (2026-10-28)
# เลือกตาม record type: FULL ได้ทุกชนิด, ที่เหลือแยกตามตาราง
TEXT_SUBRECORDS_UNIVERSAL = ("FULL",)
TEXT_SUBRECORDS_BY_TYPE = {
    "BOOK": ("DESC",),
    "MESG": ("DESC", "ITXT"),
    "GMST": ("DATA",),
    "NOTE": ("TNAM",),
    "INFO": ("NAM1", "RNAM"),          # NAM1=คำพูด, RNAM=ตัวเลือกผู้เล่นบางเคส
    "TERM": ("DESC", "ITXT", "RNAM"),  # เนื้อหา terminal / ตัวเลือก / ข้อความตอบ
    "QUST": ("NNAM",),                 # quest objective
    # Pip-Boy / item descriptions (เคยตกหล่น — มีแค่ FULL ใน Names)
    "AVIF": ("DESC",),                 # SPECIAL + Skills คำอธิบาย
    "PERK": ("DESC",),
    "WEAP": ("DESC",),
    "ARMO": ("DESC",),
    "ALCH": ("DESC",),
    "SPEL": ("DESC",),
    "MISC": ("DESC",),
    "KEYM": ("DESC",),
    "AMMO": ("DESC",),
    # รอเพิ่ม: NAM3 ของ INFO (ตรวจสอบเพิ่ม), CNAM ของ QUST (ดูเหมือน dev note)
}


def text_subrecords_for(rtype: str):
    return TEXT_SUBRECORDS_UNIVERSAL + TEXT_SUBRECORDS_BY_TYPE.get(rtype, ())

# ข้อเสนอสถิติ ( F3/FNV header record: 24 bytes )
RECORD_HEADER_SIZE = 24
GRUP_HEADER_SIZE = 24
FLAG_COMPRESSED = 0x00040000


def decompress_payload(payload: bytes, stats):
    """FNV compressed record: ลอง 2 แบบ — zlib ตรง ๆ, หรือมี uint32 (size) นำหน้า zlib stream"""
    try:
        out = zlib.decompress(payload)
        stats["compressed"] += 1
        return out
    except zlib.error:
        pass
    try:
        out = zlib.decompress(payload[4:])
        stats["compressed"] += 1
        return out
    except zlib.error:
        return None


def is_grup(data, pos: int) -> bool:
    return data[pos:pos + 4] == b"GRUP"


def walk(data, pos: int, end: int, stats, rows, opts, depth=0):
    """เดินแบบ GRUP/record ระดับใดก็ได้ (ทุกเฟสทั้งหมด)"""
    while pos < end:
        if pos + 4 > end:
            break
        sig = data[pos:pos + 4]
        if sig == b"GRUP":
            if pos + GRUP_HEADER_SIZE > end:
                break
            gsize = struct.unpack_from("<I", data, pos + 4)[0]
            if gsize <= 0 or pos + gsize > end:
                break
            walk(data, pos + GRUP_HEADER_SIZE, pos + gsize, stats, rows, opts, depth + 1)
            pos += gsize
        else:
            if pos + RECORD_HEADER_SIZE > end:
                break
            rtype = sig.decode("ascii", "replace")
            rsize = struct.unpack_from("<I", data, pos + 4)[0]
            if rsize <= 0 or pos + 24 + rsize > end:
                break
            flags = struct.unpack_from("<I", data, pos + 8)[0]
            formid = struct.unpack_from("<I", data, pos + 12)[0]
            payload = data[pos + RECORD_HEADER_SIZE: pos + 24 + rsize]
            if flags & FLAG_COMPRESSED:
                payload = decompress_payload(payload, stats)
                if payload is None:
                    stats["warn"] += 1
                    payload = b""
            parse_record(rtype, formid, payload, stats, rows, opts)
            pos += RECORD_HEADER_SIZE + rsize


def parse_record(rtype, formid, payload, stats, rows, opts):
    stats["records_seen"] += 1
    stats["by_type"][rtype] += 1
    edid = ""
    wanted = text_subrecords_for(rtype)
    n = len(payload)
    pos = 0
    while pos + 6 <= n:
        ssize = struct.unpack_from("<H", payload, pos + 4)[0]
        # ssize==0 พบบ่อย (เช่น INFO NEXT) — ข้ามต่อ ห้าม break ทั้ง record
        if pos + 6 + ssize > n:
            break
        val = payload[pos + 6: pos + 6 + ssize]
        st = payload[pos:pos + 4].decode("ascii", "replace").rstrip("\x00")
        pos += 6 + max(ssize, 0)
        if ssize == 0:
            continue
        if st == "EDID":
            edid = decode_string(val)
            stats["edid"] += 1
        elif st in wanted:
            text = decode_string(val)
            # อนุญาต \n \r \t — ข้อความ Help/MESG DESC มักมีขึ้นบรรทัดใหม่
            # (isprintable() จะตัดทั้งก้อนถ้ามี \\r\\n ทำให้ Help VDSG ตกหล่น)
            if text and _is_extractable_text(text):
                rows.append({
                    "record_type": rtype,
                    "formid": "%08X" % formid,
                    "edid": edid,
                    "subrecord": st,
                    "en": text,
                    "length": len(text),
                })
                stats["text_rows"] += 1


def _is_extractable_text(text: str) -> bool:
    for c in text:
        if c in "\n\r\t":
            continue
        if not c.isprintable():
            return False
    return True


def decode_string(value: bytes) -> str:
    # FNV เขียนข้อความแบบ single-byte codepage (ปกติ cp1252)
    # เก็บ \\r\\n ไว้ใน EN (อย่า strip หมด) — ตัดแค่ขอบนอก
    return value.split(b"\x00")[0].decode("cp1252", "replace").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin")
    ap.add_argument("--out", default="extracted.csv")
    ap.add_argument("--stats-only", action="store_true")
    args = ap.parse_args()

    with open(args.plugin, "rb") as f:
        data = f.read()

    stats = {
        "records_seen": 0,
        "edid": 0,
        "text_rows": 0,
        "dialogue_related": 0,
        "compressed": 0,
        "warn": 0,
        "by_type": collections.Counter(),
    }
    rows = []

    # หัวไฟล์ = TES4 record (ปรับสล็อตข้างหลัง) — ข้ามจากนั้นเดินทุกถถด
    tes4 = struct.unpack_from("<I", data, 4)[0]
    walk(data, 24 + tes4, len(data), stats, rows, args)

    print("== FNV Extractor v1 ==")
    print("file bytes : %d" % len(data))
    print("records    : %d  (edid=%d, compressed_ok=%d, warn=%d)" % (
        stats["records_seen"], stats["edid"], stats["compressed"], stats["warn"]))
    print("text rows  : %d  (FULL/DESC rows)" % stats["text_rows"])
    print("dialogue-related records (DIAL/INFO): %d" % stats["dialogue_related"])
    print("-- count by record type (top 30) --")
    for t, n in stats["by_type"].most_common(30):
        print("  %-5s %d" % (t, n))

    if not args.stats_only:
        with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=[
                "record_type", "formid", "edid", "subrecord", "en", "length"])
            w.writeheader()
            w.writerows(rows)
        print("saved: %s (%d rows)" % (args.out, len(rows)))


if __name__ == "__main__":
    main()
