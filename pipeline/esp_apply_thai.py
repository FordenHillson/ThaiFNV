#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
esp_apply_thai.py — ปรับข้อความไทยใน ESP: ตัดคำ (แทรกวรรค) + precompose

รีไรต์ขนาด subrecord/record/GRUP จริง (ไม่ pad) เพราะการตัดคำทำให้สตริงยาวขึ้น

Usage:
  python esp_apply_thai.py path\\ThaiFNV_Test.esp --in-place
  python esp_apply_thai.py path\\in.esp --out path\\out.esp --limit 28
  python esp_apply_thai.py path\\in.esp --out path\\out.esp --no-wordbreak
  python esp_apply_thai.py path\\in.esp --out path\\out.esp --no-compose
"""
from __future__ import annotations
import argparse
import os
import struct
import sys

from thai_precompose import compose_cp874, decode_thai_cp874, encode_thai_cp874
from thai_wordbreak import insert_word_spaces

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECORD_HEADER = 24
GRUP_HEADER = 24
FLAG_COMPRESSED = 0x00040000
TEXT_TYPES = {b"FULL", b"DESC", b"ITXT", b"NNAM", b"TNAM", b"NAM1", b"RNAM"}


def transform_zstring(raw: bytes, wordbreak: bool, compose: bool, limit: int, dense: bool) -> bytes:
    if not raw:
        return raw
    # decode (ขยาย precompose ถ้ามีอยู่แล้ว)
    try:
        text = decode_thai_cp874(raw)
    except Exception:
        try:
            text = raw.decode("cp874")
        except Exception:
            return raw
    if wordbreak:
        mode = "dense" if dense else "sparse"
        text = insert_word_spaces(text, mode=mode, limit=limit)
    if compose:
        return encode_thai_cp874(text)
    return text.encode("cp874", errors="replace")


def rewrite_payload(payload: bytes, opts) -> tuple[bytes, int]:
    out = bytearray()
    pos = 0
    n = len(payload)
    changes = 0
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
        if stype in TEXT_TYPES and ssize >= 2 and body.endswith(b"\x00"):
            raw = body[:-1]
            if b"\x00" not in raw:
                new_raw = transform_zstring(
                    raw, opts.wordbreak, opts.compose, opts.limit, opts.dense)
                if new_raw != raw:
                    new_body = new_raw + b"\x00"
                    changes += 1
        if len(new_body) > 0xFFFF:
            # ยาวเกิน subrecord — คงของเดิม
            new_body = body
            changes -= 1
        out.extend(stype)
        out.extend(struct.pack("<H", len(new_body)))
        out.extend(new_body)
        pos = body_end
    if pos < n:
        out.extend(payload[pos:])
    return bytes(out), changes


def rewrite_range(data: bytes, pos: int, end: int, opts) -> tuple[bytes, int]:
    out = bytearray()
    total = 0
    while pos + 4 <= end:
        tag = data[pos:pos + 4]
        if tag == b"GRUP":
            if pos + GRUP_HEADER > end:
                break
            gsize = struct.unpack_from("<I", data, pos + 4)[0]
            if gsize < GRUP_HEADER or pos + gsize > end:
                break
            inner, c = rewrite_range(data, pos + GRUP_HEADER, pos + gsize, opts)
            total += c
            header = bytearray(data[pos:pos + GRUP_HEADER])
            struct.pack_into("<I", header, 4, GRUP_HEADER + len(inner))
            out.extend(header)
            out.extend(inner)
            pos += gsize
            continue
        if pos + RECORD_HEADER > end:
            break
        rsize = struct.unpack_from("<I", data, pos + 4)[0]
        flags = struct.unpack_from("<I", data, pos + 8)[0]
        payload_end = pos + RECORD_HEADER + rsize
        if rsize < 0 or payload_end > end:
            break
        header = bytearray(data[pos:pos + RECORD_HEADER])
        payload = data[pos + RECORD_HEADER:payload_end]
        if flags & FLAG_COMPRESSED:
            out.extend(header)
            out.extend(payload)
        else:
            new_payload, c = rewrite_payload(payload, opts)
            total += c
            struct.pack_into("<I", header, 4, len(new_payload))
            out.extend(header)
            out.extend(new_payload)
        pos = payload_end
    return bytes(out), total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("esp")
    ap.add_argument("--out", default=None)
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--no-wordbreak", action="store_true")
    ap.add_argument("--no-compose", action="store_true")
    ap.add_argument("--dense", action="store_true")
    ap.add_argument("--limit", type=int, default=28,
                    help="sparse: แทรกวรรคเมื่อรันไทยยาวเกิน N ตัว (default 28)")
    args = ap.parse_args()
    opts = argparse.Namespace(
        wordbreak=not args.no_wordbreak,
        compose=not args.no_compose,
        dense=args.dense,
        limit=args.limit,
    )
    with open(args.esp, "rb") as f:
        raw = f.read()
    new, changes = rewrite_range(raw, 0, len(raw), opts)

    if args.in_place:
        bak = args.esp + ".thaiapply.bak"
        if not os.path.exists(bak):
            with open(bak, "wb") as f:
                f.write(raw)
        out_path = args.esp
    elif args.out:
        out_path = args.out
    else:
        base, ext = os.path.splitext(args.esp)
        out_path = base + "_thai" + ext

    with open(out_path, "wb") as f:
        f.write(new)
    print("wrote %s (changed strings: %d, %d → %d bytes)" % (
        out_path, changes, len(raw), len(new)))


if __name__ == "__main__":
    main()
