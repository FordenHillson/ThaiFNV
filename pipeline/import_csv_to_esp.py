#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_csv_to_esp.py — ป้อนคำแปลจาก CSV (Google Sheets) เข้า override ESP

อ่าน FalloutNV.esm หา MESG ตาม FormID ใน CSV แล้วเขียน ESP ทับข้อความ
FULL / DESC / ITXT เป็นไทย (CP874 + wordbreak + precompose)

Usage:
  python import_csv_to_esp.py extracted/sheets/from_google/FNV_Messages.csv \\
      --esm \"D:\\...\\FalloutNV.esm\" --out release/ThaiFNV_Messages.esp
"""
from __future__ import annotations
import argparse
import csv
import os
import struct
import sys
import zlib

from thai_precompose import encode_thai_cp874
from thai_wordbreak import insert_word_spaces

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECORD_HEADER = 24
GRUP_HEADER = 24
FLAG_COMPRESSED = 0x00040000

TEXT_SUBS = {b"FULL", b"DESC", b"ITXT"}


def parse_formid(s: str) -> int:
    s = (s or "").strip().replace("0x", "").replace("0X", "")
    return int(s, 16)


def load_translations(csv_path: str) -> dict[int, dict]:
    """formid → {FULL: str|None, DESC: str|None, ITXT: [str,...], edid: str}"""
    by: dict[int, dict] = {}
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        typ = (r.get("ประเภท") or r.get("type") or "").strip()
        th = (r.get("TH") or "").strip()
        if not th or th in (".", "...", "…"):
            continue
        fid_s = (r.get("FormID") or "").strip()
        if not fid_s:
            continue
        try:
            fid = parse_formid(fid_s)
        except ValueError:
            continue
        slot = by.setdefault(fid, {
            "FULL": None, "DESC": None, "ITXT": [], "edid": r.get("EditorID") or ""})
        if ":" in typ:
            sub = typ.split(":", 1)[1].strip().upper()
        else:
            sub = typ.upper()
        if sub == "ITXT":
            slot["ITXT"].append(th)
        elif sub in ("FULL", "DESC"):
            slot[sub] = th
    return by


def decompress_payload(payload: bytes) -> bytes | None:
    try:
        return zlib.decompress(payload)
    except zlib.error:
        pass
    try:
        return zlib.decompress(payload[4:])
    except zlib.error:
        return None


def encode_thai(text: str, wordbreak: bool, limit: int) -> bytes:
    if wordbreak:
        text = insert_word_spaces(text, mode="sparse", limit=limit)
    return encode_thai_cp874(text)


def patch_mesg_payload(payload: bytes, tr: dict, wordbreak: bool, limit: int) -> tuple[bytes, int]:
    """แทนที่ FULL/DESC/ITXT ตามลำดับ ITXT ใน record"""
    out = bytearray()
    pos = 0
    n = len(payload)
    changes = 0
    itxt_i = 0
    itxts = tr.get("ITXT") or []
    while pos + 6 <= n:
        stype = payload[pos:pos + 4]
        ssize = struct.unpack_from("<H", payload, pos + 4)[0]
        body_start = pos + 6
        body_end = body_start + ssize
        if body_end > n:
            out.extend(payload[pos:])
            break
        body = payload[body_start:body_end]
        new_body = body
        if stype in TEXT_SUBS and ssize >= 1:
            th = None
            if stype == b"FULL" and tr.get("FULL"):
                th = tr["FULL"]
            elif stype == b"DESC" and tr.get("DESC"):
                th = tr["DESC"]
            elif stype == b"ITXT" and itxt_i < len(itxts):
                th = itxts[itxt_i]
                itxt_i += 1
            elif stype == b"ITXT":
                itxt_i += 1
            if th is not None:
                raw = encode_thai(th, wordbreak, limit) + b"\x00"
                if len(raw) <= 0xFFFF:
                    new_body = raw
                    changes += 1
        out.extend(stype)
        out.extend(struct.pack("<H", len(new_body)))
        out.extend(new_body)
        pos = body_end
    if pos < n:
        out.extend(payload[pos:])
    return bytes(out), changes


def walk_collect(data: bytes, pos: int, end: int, wanted: set[int], found: dict[int, bytes]):
    while pos + 4 <= end:
        tag = data[pos:pos + 4]
        if tag == b"GRUP":
            if pos + GRUP_HEADER > end:
                break
            gsize = struct.unpack_from("<I", data, pos + 4)[0]
            if gsize < GRUP_HEADER or pos + gsize > end:
                break
            walk_collect(data, pos + GRUP_HEADER, pos + gsize, wanted, found)
            pos += gsize
            continue
        if pos + RECORD_HEADER > end:
            break
        rsize = struct.unpack_from("<I", data, pos + 4)[0]
        flags = struct.unpack_from("<I", data, pos + 8)[0]
        formid = struct.unpack_from("<I", data, pos + 12)[0]
        payload_end = pos + RECORD_HEADER + rsize
        if rsize < 0 or payload_end > end:
            break
        if tag == b"MESG" and formid in wanted and formid not in found:
            payload = data[pos + RECORD_HEADER:payload_end]
            header = bytearray(data[pos:pos + RECORD_HEADER])
            if flags & FLAG_COMPRESSED:
                dec = decompress_payload(payload)
                if dec is not None:
                    payload = dec
                    struct.pack_into("<I", header, 8, flags & ~FLAG_COMPRESSED)
                    struct.pack_into("<I", header, 4, len(payload))
                    found[formid] = bytes(header) + payload
            else:
                found[formid] = bytes(header) + payload
        pos = payload_end


def collect_mesg_records(esm_path: str, wanted: set[int]) -> dict[int, bytes]:
    with open(esm_path, "rb") as f:
        data = f.read()
    found: dict[int, bytes] = {}
    tes4 = struct.unpack_from("<I", data, 4)[0]
    walk_collect(data, 24 + tes4, len(data), wanted, found)
    return found


def build_tes4(num_records: int, author: str = "ThaiFNV",
               desc: str = "ThaiFNV Messages translation",
               master: str = "FalloutNV.esm") -> bytes:
    # HEDR: version 1.34, numRecords, nextObjectId
    hedr = struct.pack("<fII", 1.34, num_records, 0x0017BA3D)
    parts = [
        b"HEDR" + struct.pack("<H", 12) + hedr,
        b"CNAM" + struct.pack("<H", len(author) + 1) + author.encode("ascii") + b"\x00",
        b"SNAM" + struct.pack("<H", len(desc) + 1) + desc.encode("ascii", "replace") + b"\x00",
        b"MAST" + struct.pack("<H", len(master) + 1) + master.encode("ascii") + b"\x00",
        b"DATA" + struct.pack("<H", 8) + struct.pack("<Q", 0),
    ]
    payload = b"".join(parts)
    # 24-byte record header แบบ ThaiFNV_Test.esp
    header = struct.pack(
        "<4sIIIIHH",
        b"TES4", len(payload), 0, 0, 0, 15, 0,
    )
    return header + payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--esm", required=True, help="FalloutNV.esm")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-wordbreak", action="store_true")
    ap.add_argument("--limit", type=int, default=28)
    args = ap.parse_args()

    tr_map = load_translations(args.csv)
    print("translations for %d FormIDs" % len(tr_map))
    wanted = set(tr_map.keys())
    print("scanning %s ..." % args.esm)
    records = collect_mesg_records(args.esm, wanted)
    print("found %d / %d MESG in ESM" % (len(records), len(wanted)))

    patched: list[bytes] = []
    total_changes = 0
    missing = 0
    for fid in sorted(wanted):
        raw = records.get(fid)
        if not raw:
            missing += 1
            continue
        header = bytearray(raw[:RECORD_HEADER])
        payload = raw[RECORD_HEADER:]
        new_payload, c = patch_mesg_payload(
            payload, tr_map[fid], not args.no_wordbreak, args.limit)
        total_changes += c
        struct.pack_into("<I", header, 4, len(new_payload))
        # clear compressed just in case
        flags = struct.unpack_from("<I", header, 8)[0]
        struct.pack_into("<I", header, 8, flags & ~FLAG_COMPRESSED)
        patched.append(bytes(header) + new_payload)

    body = b"".join(patched)
    grup = struct.pack(
        "<4sI4sIII",
        b"GRUP", GRUP_HEADER + len(body), b"MESG", 0, 0, 0,
    )
    assert len(grup) == GRUP_HEADER
    grup = grup + body

    tes4 = build_tes4(len(patched))
    out = tes4 + bytes(grup)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(out)
    print("wrote %s (%d bytes, %d records, %d string patches, missing %d)" % (
        args.out, len(out), len(patched), total_changes, missing))


if __name__ == "__main__":
    main()
