#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_dialogue_spaces.py — แก้ไขช่องว่างคำแตกในบทสนทนา (ขนาด ไหน -> ขนาดไหน, เลือกชื่อ นี้ -> เลือกชื่อนี้)
ใน ThaiFNV.esp พร้อมอัปเดต header และ subrecord size ให้ถูกต้องสมบูรณ์

Usage:
  python patch_dialogue_spaces.py
  python patch_dialogue_spaces.py --deploy
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from thai_precompose import encode_thai_cp874, decode_thai_cp874

DEFAULT_ESP = ROOT / "release" / "ThaiFNV.esp"
GAME_DATA_ESP = Path(r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\ThaiFNV.esp")

REPLACEMENTS = [
    (encode_thai_cp874("ขนาด ไหน"), encode_thai_cp874("ขนาดไหน")),
    (encode_thai_cp874("เลือกชื่อ นี้"), encode_thai_cp874("เลือกชื่อนี้")),
]


def patch_record_payload(payload: bytes) -> tuple[bytes, int]:
    """แกะ subrecords ใน record payload แล้วแทนที่คำ พร้อมอัปเดต subrecord size"""
    subrecs: list[bytes] = []
    pos = 0
    total_mods = 0
    while pos + 6 <= len(payload):
        st = payload[pos : pos + 4]
        ss = struct.unpack_from("<H", payload, pos + 4)[0]
        sb = payload[pos + 6 : pos + 6 + ss]
        
        # แทนที่คำใน subrecord
        mod = 0
        new_sb = sb
        for old_b, new_b in REPLACEMENTS:
            if old_b in new_sb:
                c = new_sb.count(old_b)
                new_sb = new_sb.replace(old_b, new_b)
                mod += c
        
        if mod > 0:
            total_mods += mod
            subrecs.append(st + struct.pack("<H", len(new_sb)) + new_sb)
        else:
            subrecs.append(payload[pos : pos + 6 + ss])
        pos += 6 + ss
    
    return b"".join(subrecs), total_mods


def patch_element(data: bytes, pos: int, end: int) -> tuple[bytes, int, int]:
    """คืน (patched_bytes, old_length, num_mods) สำหรับ element ที่ pos"""
    tag = data[pos : pos + 4]
    if tag == b"GRUP":
        group_size = struct.unpack_from("<I", data, pos + 4)[0]
        header = data[pos : pos + 24]
        cpos = pos + 24
        gend = pos + group_size
        children: list[bytes] = []
        group_mods = 0
        while cpos < gend:
            c_bytes, c_len, c_mods = patch_element(data, cpos, gend)
            children.append(c_bytes)
            group_mods += c_mods
            cpos += c_len
        new_body = b"".join(children)
        new_group_size = 24 + len(new_body)
        new_header = bytearray(header)
        struct.pack_into("<I", new_header, 4, new_group_size)
        return bytes(new_header) + new_body, group_size, group_mods
    else:
        # Normal Record
        rec_size = struct.unpack_from("<I", data, pos + 4)[0]
        header = data[pos : pos + 24]
        payload = data[pos + 24 : pos + 24 + rec_size]
        new_payload, mods = patch_record_payload(payload)
        if mods > 0:
            new_header = bytearray(header)
            struct.pack_into("<I", new_header, 4, len(new_payload))
            return bytes(new_header) + new_payload, 24 + rec_size, mods
        else:
            return data[pos : pos + 24 + rec_size], 24 + rec_size, 0


def patch_esp(esp_path: Path):
    print(f"Patching {esp_path}...")
    data = esp_path.read_bytes()
    pos = 0
    elements: list[bytes] = []
    total_mods = 0
    while pos < len(data):
        el_bytes, el_len, el_mods = patch_element(data, pos, len(data))
        elements.append(el_bytes)
        total_mods += el_mods
        pos += el_len
    
    out_data = b"".join(elements)
    esp_path.write_bytes(out_data)
    print(f"Finished patching {esp_path.name}: {total_mods} occurrences fixed. New file size: {len(out_data)} bytes.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deploy", action="store_true", help="Deploy directly to Fallout New Vegas Data folder")
    args = parser.parse_args()

    patch_esp(DEFAULT_ESP)
    if args.deploy or GAME_DATA_ESP.exists():
        patch_esp(GAME_DATA_ESP)
        print(f"Deployed successfully to {GAME_DATA_ESP}")


if __name__ == "__main__":
    main()
