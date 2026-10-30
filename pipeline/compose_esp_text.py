#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compose_esp_text.py — แทนที่สระบน+วรรณยุกต์ใน ESP เป็นช่อง precompose (0x80–0x9B)

เดิน GRUP/record จริง (ไม่คลาย zlib): หา zstring ใน FULL/DESC/ITXT/...
compose แล้ว pad ด้วย 0x00 ให้ยาวเท่าเดิม → ไม่ต้องเลื่อนขนาด record/GRUP

เกมอ่าน zstring ถึง null ตัวแรก จึงได้ข้อความที่สั้นลงถูกต้อง

Usage:
  python compose_esp_text.py path\\ThaiFNV_Test.esp --in-place
  python compose_esp_text.py path\\FalloutNV_Thai.esp --out path\\FalloutNV_Thai_pre.esp
"""
from __future__ import annotations
import argparse
import os
import struct
import sys

from thai_precompose import compose_cp874

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECORD_HEADER = 24
GRUP_HEADER = 24
FLAG_COMPRESSED = 0x00040000

# ไม่รวม DATA — GMST อาจเป็น float/int
TEXT_TYPES = {b"FULL", b"DESC", b"ITXT", b"NNAM", b"TNAM", b"NAM1", b"RNAM"}


def _compose_body(body: bytes) -> tuple[bytes | None, bool]:
    """คืน (body ใหม่ยาวเท่าเดิม, เปลี่ยนหรือไม่) หรือ (None, False) ถ้าไม่ใช่ zstring"""
    if len(body) < 2 or not body.endswith(b"\x00"):
        return None, False
    raw = body[:-1]
    if b"\x00" in raw:
        return None, False
    composed = compose_cp874(raw)
    if composed == raw:
        return None, False
    if len(composed) > len(raw):
        return None, False
    # composed + pad nulls + terminator เดิม → ยาวเท่า body; เกมอ่านถึง null แรก
    pad = len(raw) - len(composed)
    padded = composed + (b"\x00" * pad) + b"\x00"
    assert len(padded) == len(body)
    return padded, True


def patch_payload(payload: bytearray, base_off: int = 0) -> int:
    """แก้ zstring ใน payload ของ record หนึ่งตัว (in-place) คืนจำนวนครั้งที่เปลี่ยน"""
    changes = 0
    pos = 0
    n = len(payload)
    while pos + 6 <= n:
        stype = bytes(payload[pos:pos + 4])
        ssize = struct.unpack_from("<H", payload, pos + 4)[0]
        body_start = pos + 6
        body_end = body_start + ssize
        if body_end > n:
            break
        if stype in TEXT_TYPES:
            body = bytes(payload[body_start:body_end])
            new_body, changed = _compose_body(body)
            if changed and new_body is not None:
                payload[body_start:body_end] = new_body
                changes += 1
        pos = body_end
    return changes


def patch_file(data: bytearray, pos: int, end: int) -> int:
    """เดิน GRUP/record ในช่วง [pos, end) แก้ in-place คืนจำนวน string ที่ compose"""
    total = 0
    while pos + 4 <= end:
        tag = bytes(data[pos:pos + 4])
        if tag == b"GRUP":
            if pos + GRUP_HEADER > end:
                break
            gsize = struct.unpack_from("<I", data, pos + 4)[0]
            if gsize < GRUP_HEADER or pos + gsize > end:
                break
            total += patch_file(data, pos + GRUP_HEADER, pos + gsize)
            pos += gsize
            continue
        if pos + RECORD_HEADER > end:
            break
        rsize = struct.unpack_from("<I", data, pos + 4)[0]
        flags = struct.unpack_from("<I", data, pos + 8)[0]
        payload_start = pos + RECORD_HEADER
        payload_end = payload_start + rsize
        if rsize < 0 or payload_end > end:
            break
        if not (flags & FLAG_COMPRESSED):
            # ตัด payload เป็น view ผ่าน memoryview ไม่ได้ assign — copy slice
            payload = bytearray(data[payload_start:payload_end])
            c = patch_payload(payload)
            if c:
                data[payload_start:payload_end] = payload
                total += c
        pos = payload_end
    return total


def main():
    ap = argparse.ArgumentParser(description="Precompose Thai upper+tone in ESP text")
    ap.add_argument("esp")
    ap.add_argument("--out", default=None)
    ap.add_argument("--in-place", action="store_true")
    args = ap.parse_args()

    with open(args.esp, "rb") as f:
        raw = f.read()
    data = bytearray(raw)
    changes = patch_file(data, 0, len(data))

    if args.in_place:
        bak = args.esp + ".precompose.bak"
        if not os.path.exists(bak):
            with open(bak, "wb") as f:
                f.write(raw)
        out_path = args.esp
    elif args.out:
        out_path = args.out
    else:
        base, ext = os.path.splitext(args.esp)
        out_path = base + "_precompose" + ext

    with open(out_path, "wb") as f:
        f.write(data)
    print("wrote %s (composed strings: %d, size=%d)" % (out_path, changes, len(data)))


if __name__ == "__main__":
    main()
