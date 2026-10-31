#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_csv_to_esp.py — ป้อนคำแปลจาก CSV (Google Sheets) เข้า override ESP

อ่าน FalloutNV.esm หา record ตาม FormID แล้วเขียน ESP ทับข้อความเป็นไทย
(CP874 + wordbreak + precompose)

Usage:
  # แบบเดิม (Messages)
  python import_csv_to_esp.py extracted/sheets/from_google/FNV_Messages.csv \\
      --esm \"D:\\...\\FalloutNV.esm\" --out release/ThaiFNV_Messages.esp

  # หลายหมวด (เทสเบื้องต้น)
  python import_csv_to_esp.py --csv-dir extracted/sheets/from_google \\
      --tabs FNV_Messages,FNV_Names,FNV_Notes,FNV_Quests,FNV_Terminals,FNV_BookDesc,FNV_SystemStr,FNV_Dialogue,FNV_TopicNames \\
      --esm \"D:\\...\\FalloutNV.esm\" --out release/ThaiFNV.esp
"""
from __future__ import annotations

import argparse
import csv
import os
import struct
import sys
import zlib
from collections import defaultdict
from pathlib import Path

from thai_precompose import encode_thai_cp874
from thai_wordbreak import insert_word_spaces

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECORD_HEADER = 24
GRUP_HEADER = 24
FLAG_COMPRESSED = 0x00040000

# sub ที่เป็นรายการ (หลายอันต่อ record) — จับคู่ด้วย EN ต้นฉบับ
LIST_SUBS = {b"ITXT", b"RNAM", b"NNAM", b"NAM1"}
# sub ค่าเดียวต่อ record
SINGLE_SUBS = {b"FULL", b"DESC", b"TNAM", b"DATA"}
TEXT_SUBS = LIST_SUBS | SINGLE_SUBS


def parse_formid(s: str) -> int:
    s = (s or "").strip().replace("0x", "").replace("0X", "")
    return int(s, 16)


def is_bad_formid(fid: str) -> bool:
    fid = (fid or "").strip()
    if not fid or fid in ("0", "0.0", "0.00E+00"):
        return True
    s = fid.replace("0x", "").replace("0X", "")
    if "E+" in s.upper() or "E-" in s.upper() or "." in s:
        return True
    try:
        int(s, 16)
        return False
    except ValueError:
        return True


def decode_zstring(body: bytes) -> str:
    raw = body.split(b"\x00", 1)[0]
    return raw.decode("cp1252", errors="replace")


def encode_thai(text: str, wordbreak: bool, limit: int) -> bytes:
    if wordbreak:
        text = insert_word_spaces(text, mode="sparse", limit=limit)
    return encode_thai_cp874(text)


def load_csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if "ID" not in r and "I" in r:
            r = dict(r)
            r["ID"] = r.pop("I")
        out.append(r)
    return out


def load_translations(paths: list[Path]) -> dict[int, dict]:
    """
    formid → {
      tag: bytes (record type),
      single: {b'FULL': th, ...},
      by_en: {b'NAM1': {en: th}},
      order: {b'ITXT': [th, ...]},  # fallback ถ้า EN ไม่ตรง
    }
    """
    by: dict[int, dict] = {}
    skipped_status = 0
    skipped_empty = 0
    skipped_fid = 0
    for path in paths:
        rows = load_csv_rows(path)
        for r in rows:
            st = (r.get("สถานะ") or "").strip().lower()
            if st == "skip":
                skipped_status += 1
                continue
            th = (r.get("TH") or "").strip()
            if not th or th in (".", "...", "…"):
                skipped_empty += 1
                continue
            fid_s = (r.get("FormID") or "").strip()
            if is_bad_formid(fid_s):
                skipped_fid += 1
                continue
            try:
                fid = parse_formid(fid_s)
            except ValueError:
                skipped_fid += 1
                continue
            typ = (r.get("ประเภท") or r.get("type") or "").strip()
            if ":" in typ:
                rtype, sub = typ.split(":", 1)
            else:
                rtype, sub = typ, ""
            rtype = rtype.strip().upper()
            sub = sub.strip().upper()
            if not rtype or not sub:
                continue
            tag = rtype.encode("ascii")
            if len(tag) != 4:
                # pad/truncate rare — skip odd
                continue
            slot = by.setdefault(
                fid,
                {
                    "tag": tag,
                    "single": {},
                    "by_en": defaultdict(dict),
                    "order": defaultdict(list),
                },
            )
            if slot["tag"] != tag:
                # FormID ชนกันข้ามชนิด — เก็บชนิดแรก
                continue
            sub_b = sub.encode("ascii")
            en = r.get("EN") or ""
            if sub_b in LIST_SUBS:
                slot["by_en"][sub_b][en] = th
                slot["order"][sub_b].append(th)
            elif sub_b in SINGLE_SUBS:
                slot["single"][sub_b] = th
    print(
        "translations: %d FormIDs (skip status=%d empty_th=%d bad_fid=%d)"
        % (len(by), skipped_status, skipped_empty, skipped_fid)
    )
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


def patch_payload(payload: bytes, tr: dict, wordbreak: bool, limit: int) -> tuple[bytes, int]:
    out = bytearray()
    pos = 0
    n = len(payload)
    changes = 0
    order_i: dict[bytes, int] = defaultdict(int)
    while pos + 6 <= n:
        stype = payload[pos : pos + 4]
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
            if stype in SINGLE_SUBS:
                th = tr["single"].get(stype)
            elif stype in LIST_SUBS:
                en_map = tr["by_en"].get(stype) or {}
                if en_map:
                    en = decode_zstring(body)
                    th = en_map.get(en)
                if th is None:
                    lst = tr["order"].get(stype) or []
                    idx = order_i[stype]
                    if idx < len(lst):
                        th = lst[idx]
                    order_i[stype] = idx + 1
                else:
                    order_i[stype] += 1
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


def walk_collect(
    data: bytes,
    pos: int,
    end: int,
    wanted: set[int],
    found: dict[int, tuple[bytes, bytes]],
):
    """found[formid] = (tag4, full_record_bytes_uncompressed)"""
    while pos + 4 <= end:
        tag = data[pos : pos + 4]
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
        if formid in wanted and formid not in found:
            payload = data[pos + RECORD_HEADER : payload_end]
            header = bytearray(data[pos : pos + RECORD_HEADER])
            if flags & FLAG_COMPRESSED:
                dec = decompress_payload(payload)
                if dec is not None:
                    payload = dec
                    struct.pack_into("<I", header, 8, flags & ~FLAG_COMPRESSED)
                    struct.pack_into("<I", header, 4, len(payload))
                    found[formid] = (bytes(tag), bytes(header) + payload)
            else:
                found[formid] = (bytes(tag), bytes(header) + payload)
        pos = payload_end


def collect_records(esm_path: str, wanted: set[int]) -> dict[int, tuple[bytes, bytes]]:
    with open(esm_path, "rb") as f:
        data = f.read()
    found: dict[int, tuple[bytes, bytes]] = {}
    tes4 = struct.unpack_from("<I", data, 4)[0]
    walk_collect(data, 24 + tes4, len(data), wanted, found)
    return found


def build_tes4(
    num_records: int,
    author: str = "ThaiFNV",
    desc: str = "ThaiFNV translation preview",
    master: str = "FalloutNV.esm",
) -> bytes:
    hedr = struct.pack("<fII", 1.34, num_records, 0x0017BA3D)
    parts = [
        b"HEDR" + struct.pack("<H", 12) + hedr,
        b"CNAM" + struct.pack("<H", len(author) + 1) + author.encode("ascii") + b"\x00",
        b"SNAM"
        + struct.pack("<H", len(desc) + 1)
        + desc.encode("ascii", "replace")
        + b"\x00",
        b"MAST" + struct.pack("<H", len(master) + 1) + master.encode("ascii") + b"\x00",
        b"DATA" + struct.pack("<H", 8) + struct.pack("<Q", 0),
    ]
    payload = b"".join(parts)
    header = struct.pack(
        "<4sIIIIHH",
        b"TES4",
        len(payload),
        0,
        0,
        0,
        15,
        0,
    )
    return header + payload


def build_esp(tr_map: dict[int, dict], records: dict[int, tuple[bytes, bytes]],
              wordbreak: bool, limit: int, out_path: str) -> None:
    # group patched records by tag
    by_tag: dict[bytes, list[bytes]] = defaultdict(list)
    total_changes = 0
    missing = 0
    tag_mismatch = 0
    for fid in sorted(tr_map.keys()):
        got = records.get(fid)
        if not got:
            missing += 1
            continue
        tag, raw = got
        expect = tr_map[fid]["tag"]
        if tag != expect:
            tag_mismatch += 1
            continue
        header = bytearray(raw[:RECORD_HEADER])
        payload = raw[RECORD_HEADER:]
        new_payload, c = patch_payload(payload, tr_map[fid], wordbreak, limit)
        if c == 0:
            continue
        total_changes += c
        struct.pack_into("<I", header, 4, len(new_payload))
        flags = struct.unpack_from("<I", header, 8)[0]
        struct.pack_into("<I", header, 8, flags & ~FLAG_COMPRESSED)
        by_tag[tag].append(bytes(header) + new_payload)

    grups = []
    n_rec = 0
    for tag in sorted(by_tag.keys()):
        body = b"".join(by_tag[tag])
        n_rec += len(by_tag[tag])
        grup = struct.pack(
            "<4sI4sIII",
            b"GRUP",
            GRUP_HEADER + len(body),
            tag,
            0,
            0,
            0,
        ) + body
        grups.append(grup)
        print("  GRUP %s records=%d bytes=%d" % (tag.decode("ascii"), len(by_tag[tag]), len(grup)))

    tes4 = build_tes4(n_rec)
    out = tes4 + b"".join(grups)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(out)
    print(
        "wrote %s (%d bytes, %d records, %d string patches, missing %d, tag_mismatch %d)"
        % (out_path, len(out), n_rec, total_changes, missing, tag_mismatch)
    )


def resolve_csv_paths(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []
    if args.csv:
        paths.append(Path(args.csv))
    if args.csv_dir:
        d = Path(args.csv_dir)
        if args.tabs:
            names = [t.strip() for t in args.tabs.split(",") if t.strip()]
            for name in names:
                p = d / (name if name.endswith(".csv") else f"{name}.csv")
                if not p.exists():
                    raise SystemExit("missing CSV: %s" % p)
                paths.append(p)
        else:
            paths.extend(sorted(d.glob("FNV_*.csv")))
    if not paths:
        raise SystemExit("ระบุ csv หรือ --csv-dir")
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="", help="CSV เดี่ยว (แบบเดิม)")
    ap.add_argument("--csv-dir", default="", help="โฟลเดอร์ CSV หลายไฟล์")
    ap.add_argument("--tabs", default="", help="คอมมา: FNV_Names,FNV_Quests (ใช้กับ --csv-dir)")
    ap.add_argument("--esm", required=True, help="FalloutNV.esm")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-wordbreak", action="store_true")
    ap.add_argument("--limit", type=int, default=28)
    args = ap.parse_args()

    paths = resolve_csv_paths(args)
    print("CSV files: %d" % len(paths))
    for p in paths:
        print("  %s" % p)

    tr_map = load_translations(paths)
    wanted = set(tr_map.keys())
    print("scanning %s for %d FormIDs ..." % (args.esm, len(wanted)))
    records = collect_records(args.esm, wanted)
    print("found %d / %d records in ESM" % (len(records), len(wanted)))

    build_esp(tr_map, records, not args.no_wordbreak, args.limit, args.out)


if __name__ == "__main__":
    main()
