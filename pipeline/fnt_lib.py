#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fnt_lib.py — อ่าน/เขียน .fnt และ .tex ของ Fallout: New Vegas (ThaiFNV pipeline)

ได้จากการถอดไฟล์จริง (2026-10-28):
  .fnt (ขนาดหนึ่งเดียวในชุด vanilla เสมอ) = header + ตาราง glyph 256 รายการ
    header 296 bytes @0:
      +0  float 100000.0 (UnknownScale — คงค้างจากเครื่องมือเดิม)
      +4  uint32 1, uint32 1
      +12 char[?] ชื่อฟอนต์ null-terminated (เลขเล็กสุดท้ายของชื่อ = pixel size เช่น DarN_FranKleinBold_14)
      ...ปริมาณที่เหลือเป็น 0 (พื้นที่สงวน)
    glyph entry = 56 bytes = 14 × float32:
      f0      0.0 เสมอ (สังเกตจาก vanilla)
      f1      uv Y บน  (top)
      f2      uv X ซ้าย (left)
      f3      uv Y ล่าง (bottom)
      f4..f8  กรอบ quad จริง (L, T, R, B, R) — ตัวที่เกมมาใช้วาด
      f9      ความกว้าง px ที่วาดจริง
      f10     ความสูง px ของ cell (ปกติ = ความสูงฟอนต์)
      f11     = X offset (vanilla เป็น 0 ทุกตัว — สมมติฐาน: ต้องยืนยันในเกม)
      f12     = Y offset (space=8.33, dummy=2.0, ตัวอักษร=0 — สมมติฐาน: ต้องยืนยันในเกม)
      f13     = advance (ช่องกว้างที่ cursor เลื่อน)
      entry dummy (glyph ว่าง): f12=2.0, f13=0, ที่เหลือ 0
  .tex = RGBA ขนาดดิบ (ไม่ผ่าน DDS): header 8 bytes = uint32 width ×2, ตามด้วย w*h*4 bytes

ตัวใช้งาน:
  from fnt_lib import load_fnt, save_fnt, load_tex, save_tex
"""
from __future__ import annotations
import struct

HEADER_SIZE = 296
ENTRY_SIZE = 56
NUM_GLYPHS = 256

GENERIC_HEADER = b"\x00\x00\x00\x00" * 4 + b"\x01\x00\x00\x00" + b"\x01\x00\x00\x00"


class Glyph:
    __slots__ = ("uv_top", "uv_left", "uv_bottom", "uv_right",
                 "px_width", "px_height", "x_offset", "y_offset", "advance")

    def __init__(self):
        self.uv_top = self.uv_left = self.uv_bottom = self.uv_right = 0.0
        self.px_width = self.px_height = 0.0
        self.x_offset = self.y_offset = 0.0
        self.advance = 0.0

    def pack(self) -> bytes:
        # ประกอบตามเทียบ vanilla: f0=0, f1=T, f2=L, f3=B, f4=L, f5=T, f6=R, f7=B, f8=R
        return struct.pack(
            "<14f",
            0.0,
            self.uv_top,
            self.uv_left,
            self.uv_bottom,
            self.uv_left,
            self.uv_top,
            self.uv_right,
            self.uv_bottom,
            self.uv_right,
            self.px_width,
            self.px_height,
            self.x_offset,
            self.y_offset,
            self.advance,
        )

    @classmethod
    def unpack(cls, raw: bytes) -> "Glyph":
        f = struct.unpack_from("<14f", raw)
        g = cls()
        g.uv_top, g.uv_left, g.uv_bottom, g.uv_right = f[1], f[2], f[3], f[6]
        g.px_width, g.px_height = f[9], f[10]
        g.x_offset, g.y_offset, g.advance = f[11], f[12], f[13]
        return g


def load_fnt(path: str):
    """คืน (name, glyphs[list 256])"""
    with open(path, "rb") as f:
        data = f.read()
    name = data[12:60].split(b"\x00")[0].decode("ascii", "replace")
    glyphs = [Glyph.unpack(data[HEADER_SIZE + i * ENTRY_SIZE:
                             HEADER_SIZE + (i + 1) * ENTRY_SIZE])
              for i in range(NUM_GLYPHS)]
    return name, glyphs


def save_fnt(path: str, name: str, glyphs, scale=100000.0):
    assert len(glyphs) == NUM_GLYPHS
    header = struct.pack("<fII", scale, 1, 1)
    raw_name = name.encode("ascii")[:47] + b"\x00"
    header += raw_name
    header = header.ljust(HEADER_SIZE, b"\x00")[:HEADER_SIZE]
    with open(path, "wb") as f:
        f.write(header)
        for g in glyphs:
            f.write(g.pack())


def load_tex(path: str):
    """คืน (width, height, bytes RGBA ดิบ w*h*4)"""
    with open(path, "rb") as f:
        data = f.read()
    w, h = struct.unpack_from("<II", data, 0)
    return w, h, data[8:8 + w * h * 4]


def save_tex(path: str, w: int, h: int, rgba: bytes):
    assert len(rgba) == w * h * 4
    with open(path, "wb") as f:
        f.write(struct.pack("<II", w, h))
        f.write(rgba)
