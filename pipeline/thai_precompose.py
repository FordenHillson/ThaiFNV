#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thai_precompose.py — map สระบน+วรรณยุกต์ → ช่อง CP874 ว่าง (ชั้น 3)

เกมไม่มี shaping: ี+่ เป็น 2 glyph วางข้างกัน (แบบ FNVThai)
แก้โดยรวมเป็น 1 combining glyph ในช่องว่าง 0x80–0x9B แล้วแทนที่ในข้อความ

Usage:
  from thai_precompose import compose_cp874, expand_cp874, PRECOMPOSE_TABLE
  composed = compose_cp874(raw_cp874_bytes)
"""
from __future__ import annotations

# สระบน × วรรณยุกต์ (28 ชุด) → ช่องว่าง CP874 ที่ไม่ใช่ไทยมาตรฐาน
UPPER_VOWELS = "ัิีึื็ํ"
TONE_MARKS = "่้๊๋"

# เรียงคงที่: ทุกสระบน × ทุกวรรณยุกต์ (4) = 28
_COMBOS: list[str] = [u + t for u in UPPER_VOWELS for t in TONE_MARKS]
_SLOTS: list[int] = list(range(0x80, 0x80 + len(_COMBOS)))  # 0x80..0x9B

assert len(_COMBOS) == len(_SLOTS) == 28

# cluster unicode → byte, และกลับ
PRECOMPOSE_TABLE: dict[str, int] = dict(zip(_COMBOS, _SLOTS))
PRECOMPOSE_BYTE_TO_CLUSTER: dict[int, str] = {b: c for c, b in PRECOMPOSE_TABLE.items()}


def is_precompose_slot(cp: int) -> bool:
    return cp in PRECOMPOSE_BYTE_TO_CLUSTER


def cluster_of_slot(cp: int) -> str | None:
    return PRECOMPOSE_BYTE_TO_CLUSTER.get(cp)


def compose_text(text: str) -> str:
    """แทนที่สระบน+วรรณยุกต์ในสตริง Unicode ด้วยตัวอักษรจากช่อง precompose
    (ใช้ chr(byte) เป็น proxy ใน Python — ตอน encode cp874 ต้อง map เอง)
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if i + 1 < n:
            pair = text[i] + text[i + 1]
            if pair in PRECOMPOSE_TABLE:
                # เก็บเป็น private marker ผ่าน chr ของ slot (latin-1)
                out.append(chr(PRECOMPOSE_TABLE[pair]))
                i += 2
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def expand_text(text: str) -> str:
    """คืนสตริงที่มี chr(slot) กลับเป็นสระ+วรรณยุกต์"""
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if o in PRECOMPOSE_BYTE_TO_CLUSTER:
            out.append(PRECOMPOSE_BYTE_TO_CLUSTER[o])
        else:
            out.append(ch)
    return "".join(out)


def compose_cp874(data: bytes) -> bytes:
    """แทนที่ลำดับ byte สระบน+วรรณยุกต์ใน CP874 เป็นช่อง precompose"""
    # map unicode combining → cp874 byte
    u_to_b: dict[str, int] = {}
    for cp in range(0xA0, 0x100):
        try:
            ch = bytes([cp]).decode("cp874")
        except UnicodeDecodeError:
            continue
        u_to_b[ch] = cp
    upper_b = {u_to_b[u] for u in UPPER_VOWELS if u in u_to_b}
    tone_b = {u_to_b[t] for t in TONE_MARKS if t in u_to_b}
    pair_to_slot: dict[tuple[int, int], int] = {}
    for cluster, slot in PRECOMPOSE_TABLE.items():
        ub, tb = u_to_b.get(cluster[0]), u_to_b.get(cluster[1])
        if ub is not None and tb is not None:
            pair_to_slot[(ub, tb)] = slot

    out = bytearray()
    i = 0
    while i < len(data):
        if i + 1 < len(data):
            key = (data[i], data[i + 1])
            if key in pair_to_slot:
                out.append(pair_to_slot[key])
                i += 2
                continue
        out.append(data[i])
        i += 1
    return bytes(out)


def expand_cp874(data: bytes) -> bytes:
    """คืนช่อง precompose ใน CP874 กลับเป็น 2 byte สระ+วรรณยุกต์"""
    u_to_b: dict[str, int] = {}
    for cp in range(0xA0, 0x100):
        try:
            ch = bytes([cp]).decode("cp874")
        except UnicodeDecodeError:
            continue
        u_to_b[ch] = cp
    out = bytearray()
    for b in data:
        if b in PRECOMPOSE_BYTE_TO_CLUSTER:
            cluster = PRECOMPOSE_BYTE_TO_CLUSTER[b]
            out.append(u_to_b[cluster[0]])
            out.append(u_to_b[cluster[1]])
        else:
            out.append(b)
    return bytes(out)


def encode_thai_cp874(text: str) -> bytes:
    """Unicode → CP874 พร้อม precompose"""
    return compose_cp874(text.encode("cp874", errors="replace"))


def decode_thai_cp874(data: bytes) -> str:
    """CP874 (อาจมี precompose) → Unicode ปกติ"""
    return expand_cp874(data).decode("cp874", errors="replace")


if __name__ == "__main__":
    samples = ["ที่", "ชิ้น", "เปลี่ยน", "ถูกต้อง", "เซอร์"]
    for s in samples:
        raw = s.encode("cp874")
        comp = compose_cp874(raw)
        back = expand_cp874(comp).decode("cp874")
        print("%s raw=%s comp=%s back=%s ok=%s" % (
            s, raw.hex(), comp.hex(), back, back == s))
    print("slots:", ", ".join("0x%02X=%s" % (b, c) for c, b in PRECOMPOSE_TABLE.items()))
