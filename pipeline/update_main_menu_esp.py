#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_main_menu_esp.py — ปรับปรุงหรือเพิ่ม GMST ใน ThaiFNV.esp จาก FNV_MainMenu_UI.csv

Usage:
  python update_main_menu_esp.py
  python update_main_menu_esp.py --deploy
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from thai_shaper_engine import shape_to_bytes

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CSV_PATH = ROOT / "extracted" / "by_category" / "FNV_MainMenu_UI.csv"
DEFAULT_ESP = ROOT / "release" / "ThaiFNV.esp"
GAME_DATA = Path(r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data")


def make_gmst(formid: int, edid: str, th: str) -> bytes:
    edid_b = edid.encode("ascii") + b"\x00"
    data_b = shape_to_bytes(th) + b"\x00"
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
        0,  # flags
        formid,
        0,  # vc
        15, # formVersion
        0,
    )
    return header + payload


def update_esp(esp_path: Path, csv_path: Path) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    if not esp_path.exists():
        raise FileNotFoundError(f"ESP not found: {esp_path}")

    df = pd.read_csv(csv_path)
    # กรองเฉพาะแถวที่มี EditorID และ TH
    strings = {}
    for _, row in df.iterrows():
        edid = str(row["EditorID"]).strip()
        th = str(row["TH"]).strip()
        if edid and th and th != "nan":
            # ปรับแต่ง linebreak พิเศษสำหรับ confirm popup ให้พอดีกับความกว้างกรอบ ไม่โดนตัดคำ
            if edid == "sConfirmNew":
                th = "เริ่มเกมใหม่ใช่หรือไม่?\nการกระทำนี้จะเขียนทับ\nเซฟอัตโนมัติหากมีอยู่"
            strings[edid] = th

    print(f"Loaded {len(strings)} strings from {csv_path.name}")

    data = bytearray(esp_path.read_bytes())
    tes4_size = struct.unpack_from("<I", data, 4)[0]
    tes4_end = 24 + tes4_size

    # หาตำแหน่ง HEDR ใน TES4
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
    print(f"Current HEDR: num_records={num_records}, next_obj=0x{next_obj:08X}")

    # หา GMST GRUP
    pos = tes4_end
    gmst_pos = None
    gmst_size = 0
    while pos + 24 <= len(data):
        if data[pos : pos + 4] != b"GRUP":
            break
        gsize = struct.unpack_from("<I", data, pos + 4)[0]
        label = bytes(data[pos + 8 : pos + 12])
        if label == b"GMST":
            gmst_pos = pos
            gmst_size = gsize
            break
        pos += gsize

    if gmst_pos is None:
        raise SystemExit("GMST GRUP not found in ESP")

    # แตก GMST records ทีละตัว
    grup_header = data[gmst_pos : gmst_pos + 24]
    grup_body = data[gmst_pos + 24 : gmst_pos + gmst_size]

    records = []
    cur = 0
    updated_edids = set()

    while cur + 24 <= len(grup_body):
        rec_type = grup_body[cur : cur + 4]
        rec_size = struct.unpack_from("<I", grup_body, cur + 4)[0]
        rec_header = grup_body[cur : cur + 24]
        formid = struct.unpack_from("<I", rec_header, 12)[0]
        payload = grup_body[cur + 24 : cur + 24 + rec_size]

        # แกะ subrecords
        ppos = 0
        edid = ""
        subrecs = []
        while ppos + 6 <= len(payload):
            st = payload[ppos : ppos + 4]
            ss = struct.unpack_from("<H", payload, ppos + 4)[0]
            sb = payload[ppos + 6 : ppos + 6 + ss]
            subrecs.append((st, sb))
            if st == b"EDID":
                edid = sb.decode("ascii", errors="ignore").rstrip("\x00")
            ppos += 6 + ss

        # ถ้า edid อยู่ใน strings เราจะอัปเดต DATA
        if edid in strings:
            new_th = strings[edid]
            new_data_b = shape_to_bytes(new_th) + b"\x00"
            new_subrecs = []
            for st, sb in subrecs:
                if st == b"DATA":
                    new_subrecs.append((st, new_data_b))
                else:
                    new_subrecs.append((st, sb))
            # ประกอบ payload ใหม่
            new_payload = b"".join(st + struct.pack("<H", len(sb)) + sb for st, sb in new_subrecs)
            new_rec_header = bytearray(rec_header)
            struct.pack_into("<I", new_rec_header, 4, len(new_payload))
            records.append(bytes(new_rec_header) + new_payload)
            updated_edids.add(edid)
            print(f"  [UPDATE] {edid} (0x{formid:08X}) -> {new_th}")
        else:
            records.append(bytes(rec_header) + payload)

        cur += 24 + rec_size

    # สำหรับ edids ที่ยังไม่มีใน GRUP ให้สร้างใหม่
    new_edids = [k for k in strings if k not in updated_edids]
    base_fid = 0x01000001
    if (next_obj & 0xFF000000) == 0x01000000:
        base_fid = max(base_fid, next_obj)

    for i, edid in enumerate(new_edids):
        fid = base_fid + i
        th_val = strings[edid]
        rec = make_gmst(fid, edid, th_val)
        records.append(rec)
        print(f"  [CREATE] {edid} (0x{fid:08X}) -> {th_val}")

    new_grup_body = b"".join(records)
    new_gmst_size = 24 + len(new_grup_body)
    new_grup_header = bytearray(grup_header)
    struct.pack_into("<I", new_grup_header, 4, new_gmst_size)
    new_grup = bytes(new_grup_header) + new_grup_body

    # แทนที่ GMST GRUP เดิมใน data
    data[gmst_pos : gmst_pos + gmst_size] = new_grup

    # อัปเดต HEDR
    added_count = len(new_edids)
    if added_count > 0:
        struct.pack_into("<I", data, hedr_pos + 4, num_records + added_count)
        struct.pack_into("<I", data, hedr_pos + 8, base_fid + added_count)

    esp_path.write_bytes(data)
    print(f"\nSuccessfully updated {esp_path.name}: {len(updated_edids)} updated, {added_count} created.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default=str(DEFAULT_ESP))
    ap.add_argument("--csv", default=str(CSV_PATH))
    ap.add_argument("--deploy", action="store_true", help="Copy to Fallout New Vegas Data folder")
    args = ap.parse_args()

    esp_path = Path(args.esp)
    csv_path = Path(args.csv)
    update_esp(esp_path, csv_path)

    if args.deploy:
        dest = GAME_DATA / "ThaiFNV.esp"
        dest.write_bytes(esp_path.read_bytes())
        print(f"Deployed -> {dest}")


if __name__ == "__main__":
    main()
