#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bsa_extract.py — ดึงไฟล์จาก .bsa ของ Fallout: New Vegas (อ่านล้วน ไม่แตะ archive)

ใช้เมื่อต้องได้ .fnt/.tex ต้นฉบับมาเป็น reference (ดู docs/2026-10-28-fnt-format-fix.md)

รูปแบบ BSA (Bethesda v103/104, FNV = 0x67):
  header 36 bytes: magic 'BSA\\0', version, folderOffset, archiveFlags,
                   folderCount, fileCount, totalFolderNameLength,
                   totalFileNameLength, fileFlags
  folder records 16 bytes: hash u64, count u32, offset u32
  ตามด้วย folder name (1 byte length + ชื่อ + NUL) และ file records 16 bytes
  (hash u64, size u32, offset u32) แล้วค่อยตามชื่อไฟล์ทั้งหมด
  ไฟล์ที่บีบอัด: zlib + ชื่อไฟล์ฝังอยู่ข้างหน้า (archiveFlags & 0x100)

Usage:
  python bsa_extract.py "D:\\...\\Fallout - Textures2.bsa" --filter fonts --out ..\\testing\\vanilla_bsa_fonts
  python bsa_extract.py game.bsa --list
"""
from __future__ import annotations
import argparse
import os
import struct
import sys
import zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_index(data: bytes):
    magic, version, folder_off, flags, folder_count, file_count = \
        struct.unpack_from("<4sIIIII", data, 0)
    if magic != b"BSA\x00":
        raise SystemExit("ไม่ใช่ไฟล์ BSA")

    # folder records ทั้งหมดอยู่ติดกันก่อน แล้วค่อยตาม folder name + file records
    recs = [struct.unpack_from("<QII", data, folder_off + i * 16)
            for i in range(folder_count)]
    pos = folder_off + folder_count * 16
    folders = []
    for _hash, count, _off in recs:
        n = data[pos]
        name = data[pos + 1:pos + n].rstrip(b"\x00").decode("cp1252", "replace")
        pos += 1 + n
        files = []
        for _ in range(count):
            _fh, size, doff = struct.unpack_from("<QII", data, pos)
            pos += 16
            files.append((size, doff))
        folders.append((name, files))

    # รายชื่อไฟล์ทั้งหมดเรียงตาม folder/file record
    names = []
    for _name, files in folders:
        for _ in files:
            end = data.index(b"\x00", pos)
            names.append(data[pos:end].decode("cp1252", "replace"))
            pos = end + 1

    out = []
    idx = 0
    for name, files in folders:
        for size, doff in files:
            out.append((name, names[idx], size, doff))
            idx += 1
    return flags, out


def extract(data: bytes, flags: int, name: str, size: int, off: int) -> bytes:
    raw = data[off:off + size]
    if flags & 0x100:  # ชื่อไฟล์ฝังอยู่ข้างหน้า
        n = raw[0]
        raw = raw[1 + n:]
    # ไฟล์บีบอัด: [uint32 ขนาดจริง][zlib stream]
    for cand in (raw, raw[4:]):
        try:
            return zlib.decompress(cand)
        except zlib.error:
            pass
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bsa")
    ap.add_argument("--out", default=None, help="โฟลเดอร์ปลายทาง (ต้องมีเมื่อไม่ใช้ --list)")
    ap.add_argument("--filter", default=None, help="เอาเฉพาะ path ที่มีคำนี้ (เช่น fonts)")
    ap.add_argument("--list", action="store_true", help="แสดงรายชื่อไฟล์เท่านั้น")
    args = ap.parse_args()

    with open(args.bsa, "rb") as f:
        data = f.read()
    flags, entries = read_index(data)

    picked = [e for e in entries if not args.filter or args.filter.lower() in
              (e[0] + "\\" + e[1]).lower()]
    if args.list:
        for folder, name, size, _off in picked:
            print("%s\\%s  (%d bytes)" % (folder, name, size))
        print("total:", len(picked))
        return
    if not args.out:
        ap.error("ต้องระบุ --out (หรือใช้ --list)")

    os.makedirs(args.out, exist_ok=True)
    for folder, name, size, off in picked:
        payload = extract(data, flags, name, size, off)
        dst = os.path.join(args.out, os.path.basename(name))
        with open(dst, "wb") as w:
            w.write(payload)
        print("%-45s stored=%-7d out=%-8d" % (name, size, len(payload)))
    print("done:", len(picked), "ไฟล์ →", args.out)


if __name__ == "__main__":
    main()
