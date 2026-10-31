#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_main_menu_gmst.py — เพิ่ม GMST ทับข้อความเมนูหลักที่ฝังใน FalloutNV.exe

ข้อความ Continue/New/Load/... ไม่ได้อยู่ใน ESM → ต้องสร้าง GMST ใหม่ใน ESP
ที่มี EditorID ตรงกับคีย์ใน exe (sNew, sLoad, sSettings, sCrew, ...)

Usage:
  python inject_main_menu_gmst.py --esp release/ThaiFNV.esp
  python inject_main_menu_gmst.py --esp release/ThaiFNV.esp --deploy
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from thai_precompose import encode_thai_cp874

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
GAME_DATA = Path(r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data")

# คีย์จาก string table ใน FalloutNV.exe → คำแปลไทย (เมนูหลัก)
STRINGS: dict[str, str] = {
    "sContinue": "เล่นต่อ",
    "sNew": "ใหม่",
    "sLoad": "โหลด",
    "sSettings": "การตั้งค่า",
    "sCrew": "เครดิต",
    "sQuit": "ออก",
    "sDownloads": "เนื้อหาดาวน์โหลด",
    "sSave": "บันทึก",
}


def make_gmst(formid: int, edid: str, th: str) -> bytes:
    edid_b = edid.encode("ascii") + b"\x00"
    data_b = encode_thai_cp874(th) + b"\x00"
    payload = (
        b"EDID"
        + struct.pack("<H", len(edid_b))
        + edid_b
        + b"DATA"
        + struct.pack("<H", len(data_b))
        + data_b
    )
    header = struct.pack(
        "<4sIIIIHH",
        b"GMST",
        len(payload),
        0,
        formid,
        0,
        15,
        0,
    )
    return header + payload


def inject(esp_path: Path) -> None:
    data = bytearray(esp_path.read_bytes())
    tes4_size = struct.unpack_from("<I", data, 4)[0]
    tes4_end = 24 + tes4_size

    hedr_pos = None
    pos = 24
    while pos + 6 <= tes4_end:
        st = bytes(data[pos : pos + 4])
        ss = struct.unpack_from("<H", data, pos + 4)[0]
        if st == b"HEDR" and ss == 12:
            hedr_pos = pos + 6
            break
        pos += 6 + ss
    if hedr_pos is None:
        raise SystemExit("HEDR not found")

    num_records = struct.unpack_from("<I", data, hedr_pos + 4)[0]
    next_obj = struct.unpack_from("<I", data, hedr_pos + 8)[0]
    print("before HEDR num=%d next=0x%08X" % (num_records, next_obj))

    pos = tes4_end
    gmst_grup_pos = None
    gmst_grup_size = 0
    while pos + 24 <= len(data):
        if data[pos : pos + 4] != b"GRUP":
            break
        gsize = struct.unpack_from("<I", data, pos + 4)[0]
        label = bytes(data[pos + 8 : pos + 12])
        if label == b"GMST":
            gmst_grup_pos = pos
            gmst_grup_size = gsize
            break
        pos += gsize
    if gmst_grup_pos is None:
        raise SystemExit("GMST GRUP not found")

    # อย่า inject ซ้ำถ้ามี EDID เหล่านี้อยู่แล้วใน GRUP
    grup_body = bytes(data[gmst_grup_pos + 24 : gmst_grup_pos + gmst_grup_size])
    already = {edid for edid in STRINGS if edid.encode("ascii") + b"\x00" in grup_body}
    todo = {k: v for k, v in STRINGS.items() if k not in already}
    if already:
        print("skip already present: %s" % ", ".join(sorted(already)))
    if not todo:
        print("nothing to inject")
        return

    base_fid = 0x01000001
    # เลี่ยงชนกับ nextObjectId เดิมถ้าอยู่ในช่วง 01xxxxxx
    if (next_obj & 0xFF000000) == 0x01000000:
        base_fid = max(base_fid, next_obj)

    parts: list[bytes] = []
    for i, (edid, th) in enumerate(todo.items()):
        fid = base_fid + i
        rec = make_gmst(fid, edid, th)
        parts.append(rec)
        print("  + %s fid=0x%08X → %s" % (edid, fid, th))
    blob = b"".join(parts)

    insert_at = gmst_grup_pos + gmst_grup_size
    data[insert_at:insert_at] = blob
    struct.pack_into("<I", data, gmst_grup_pos + 4, gmst_grup_size + len(blob))
    struct.pack_into("<I", data, hedr_pos + 4, num_records + len(todo))
    struct.pack_into("<I", data, hedr_pos + 8, base_fid + len(todo))

    esp_path.write_bytes(data)
    print("wrote %s (%d bytes, +%d GMST)" % (esp_path, len(data), len(todo)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default=str(ROOT / "release" / "ThaiFNV.esp"))
    ap.add_argument("--deploy", action="store_true", help="คัดลอกไป Data\\ThaiFNV.esp")
    args = ap.parse_args()
    esp = Path(args.esp)
    inject(esp)
    if args.deploy:
        dest = GAME_DATA / "ThaiFNV.esp"
        dest.write_bytes(esp.read_bytes())
        print("deployed %s" % dest)


if __name__ == "__main__":
    main()
