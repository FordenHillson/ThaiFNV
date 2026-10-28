#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inspect_subs.py — ตรวจสำรวจ signature ของ subrecord ใน FalloutNV.esm

รายงาน: ต่อ record type ระบุ: sig ทั้งหมด + จำนวน + ตัวอย่างข้อความ (ถ้าดูเป็นตัวหนังสือ)
เพื่อหา "ช่องที่เก็บข้อความจริง" ให้ระบุตัวเอง

Usage:
  python inspect_subs.py "FalloutNV.esm" --types WEAP,MISC,MESG,GMST,ARMO --deep 500
"""
from __future__ import annotations
import argparse, collections, struct, sys, zlib

RECORD_HEADER_SIZE, GRUP_HEADER_SIZE, FLAG_COMPRESSED = 24, 24, 0x00040000

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def decompress(payload):
    for blob in (payload, payload[4:]):
        try:
            return zlib.decompress(blob)
        except zlib.error:
            pass
    return b""


def printable(s: str) -> bool:
    return s and all((c.isprintable() and c not in "\r\n") for c in s)


def decode_string(v: bytes) -> str:
    return v.split(b"\x00")[0].decode("cp1252", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin")
    ap.add_argument("--types", default="WEAP,MISC,MESG,GMST,ARMO,ACTI,NOTE,BOOK,CONT,NPC_")
    ap.add_argument("--deep", type=int, default=400, help="จำกัดจำนวน record ต่อชนิด")
    args = ap.parse_args()

    targets = set(args.types.split(","))
    with open(args.plugin, "rb") as f:
        data = f.read()

    seen_count = collections.Counter()
    got = collections.defaultdict(list)  # (rtype,sig) -> list samples
    counts = collections.defaultdict(collections.Counter)  # rtype -> Counter sig

    def handle_rec(rtype, payload):
        if rtype not in targets or seen_count[rtype] >= args.deep:
            return
        seen_count[rtype] += 1
        n = len(payload)
        pos = 0
        while pos + 6 <= n:
            ssize = struct.unpack_from("<H", payload, pos + 4)[0]
            if ssize == 0 or pos + 6 + ssize > n:
                break
            val = payload[pos + 6: pos + 6 + ssize]
            sig = payload[pos:pos + 4].decode("ascii", "replace").rstrip("\x00")
            counts[rtype][sig] += 1
            if len(got[(rtype, sig)]) < 3:
                s = decode_string(val)
                if printable(s):
                    got[(rtype, sig)].append(s[:60])
            pos += 6 + ssize

    def walk(pos, end):
        while pos < end:
            sig4 = data[pos:pos + 4]
            if sig4 == b"GRUP":
                gsize = struct.unpack_from("<I", data, pos + 4)[0]
                if gsize <= 0 or pos + gsize > end:
                    break
                walk(pos + GRUP_HEADER_SIZE, pos + gsize)
                pos += gsize
            else:
                rsize = struct.unpack_from("<I", data, pos + 4)[0]
                if rsize <= 0 or pos + 24 + rsize > end:
                    break
                rtype = sig4.decode("ascii", "replace")
                flags = struct.unpack_from("<I", data, pos + 8)[0]
                payload = data[pos + 24: pos + 24 + rsize]
                if flags & FLAG_COMPRESSED:
                    payload = decompress(payload)
                handle_rec(rtype, payload)
                pos += 24 + rsize

    tes4 = struct.unpack_from("<I", data, 4)[0]
    walk(24 + tes4, len(data))

    for rtype in sorted(counts):
        print("== %s (สอดตัว %d รายการ, เดิน %d)" % (rtype, len(counts[rtype]), seen_count[rtype]))
        for sig, n in counts[rtype].most_common(25):
            samples = " | ".join(repr(x) for x in got.get((rtype, sig), []))
            print("   %-6s x%-6d %s" % (sig, n, samples))


if __name__ == "__main__":
    main()
