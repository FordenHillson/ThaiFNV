#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fnt_lib.py — อ่าน/เขียน .fnt และ .tex ของ Fallout: New Vegas (ThaiFNV pipeline)

โครงสร้างไฟล์ (ยืนยันจาก vanilla จริงใน testing/vanilla_bsa_fonts/ และตัวอ่าน
Gamebryo font ของ OpenMW: components/fontloader/fontloader.cpp — struct GlyphInfo)

  .fnt = header 296 bytes + ตาราง glyph 256 รายการ × 56 bytes
    header:
      +0    float  line height ของฟอนต์ (vanilla = 25..52 ไม่ใช่ 100000)
      +4    uint32 1
      +8    uint32 1
      +12   char[284] ชื่อ texture (null-terminated) — เกมจะไปโหลด
            Textures\\Fonts\\<ชื่อนี้>.tex
    glyph entry = 14 × float32:
      f0         0.0 (ไม่ใช้)
      f1,f2      UV มุมบนซ้าย  (left, top)
      f3,f4      UV มุมบนขวา   (right, top)
      f5,f6      UV มุมล่างซ้าย (left, bottom)
      f7,f8      UV มุมล่างขวา  (right, bottom)
                 → ช่วง UV เป็น 0..1 เทียบกับ width/height ของ .tex
      f9         width  px ของ quad (= ความกว้างกล่องหมึก)
      f10        height px ของ quad (= ความสูงกล่องหมึก)
      f11        bearing X — ระยะจาก pen ถึงขอบซ้ายของ glyph
      f12        advance ส่วนเกิน: advance จริง = width + f12
      f13        ascent — ระยะจากขอบบนของ glyph ลงมาถึง baseline
                 (quad top = baseline - ascent)

  .tex = header 8 bytes = uint32 width, height แล้วตามด้วย RGBA ดิบ w*h*4
         (row 0 = ขอบบนภาพ, ไม่มี DDS header)

หมายเหตุสำคัญ: ช่อง f11/f12/f13 เคยถูกเข้าใจผิดว่าเป็น x_offset/y_offset/advance
ทำให้ glyph ถูกวางผิดทั้งแนวตั้งและระยะเลื่อน — ดู docs/2026-10-28-fnt-format-fix.md

ตัวใช้งาน:
  from fnt_lib import load_fnt, save_fnt, load_tex, save_tex
"""
from __future__ import annotations
import struct

HEADER_SIZE = 296
ENTRY_SIZE = 56
NUM_GLYPHS = 256
NAME_SIZE = HEADER_SIZE - 12  # 284


class Glyph:
    """หนึ่งช่องในตาราง glyph (1 ช่อง = 1 byte ของข้อความในเกม)"""

    __slots__ = ("uv_left", "uv_top", "uv_right", "uv_bottom",
                 "px_width", "px_height", "bearing_x", "advance_extra", "ascent")

    def __init__(self):
        self.uv_left = self.uv_top = self.uv_right = self.uv_bottom = 0.0
        self.px_width = self.px_height = 0.0
        self.bearing_x = self.advance_extra = self.ascent = 0.0

    # advance จริงที่เกมใช้เลื่อน pen = width + advance_extra
    @property
    def advance(self) -> float:
        return self.px_width + self.advance_extra

    @advance.setter
    def advance(self, value: float):
        self.advance_extra = value - self.px_width

    def set_uv(self, left: float, top: float, right: float, bottom: float):
        self.uv_left, self.uv_top, self.uv_right, self.uv_bottom = left, top, right, bottom

    def pack(self) -> bytes:
        # 4 มุม: (L,T) (R,T) (L,B) (R,B) — ห้ามสลับ L/T เด็ดขาด
        return struct.pack(
            "<14f",
            0.0,
            self.uv_left, self.uv_top,
            self.uv_right, self.uv_top,
            self.uv_left, self.uv_bottom,
            self.uv_right, self.uv_bottom,
            self.px_width,
            self.px_height,
            self.bearing_x,
            self.advance_extra,
            self.ascent,
        )

    @classmethod
    def unpack(cls, raw: bytes) -> "Glyph":
        f = struct.unpack_from("<14f", raw)
        g = cls()
        g.uv_left, g.uv_top = f[1], f[2]
        g.uv_right, g.uv_bottom = f[3], f[6]
        g.px_width, g.px_height = f[9], f[10]
        g.bearing_x, g.advance_extra, g.ascent = f[11], f[12], f[13]
        return g

    def __repr__(self) -> str:
        return ("Glyph(uv=%.4f,%.4f,%.4f,%.4f w=%g h=%g bearing=%g adv=%g ascent=%g)"
                % (self.uv_left, self.uv_top, self.uv_right, self.uv_bottom,
                   self.px_width, self.px_height, self.bearing_x,
                   self.advance, self.ascent))


def load_fnt(path: str):
    """คืน (name, glyphs[list 256])"""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < HEADER_SIZE + NUM_GLYPHS * ENTRY_SIZE:
        raise ValueError("%s: ไฟล์สั้นเกินไป (%d bytes)" % (path, len(data)))
    line_height = struct.unpack_from("<f", data, 0)[0]
    name = data[12:12 + NAME_SIZE].split(b"\x00")[0].decode("ascii", "replace")
    glyphs = [Glyph.unpack(data[HEADER_SIZE + i * ENTRY_SIZE:
                              HEADER_SIZE + (i + 1) * ENTRY_SIZE])
              for i in range(NUM_GLYPHS)]
    return name, glyphs


def save_fnt(path: str, name: str, glyphs, line_height: float | None = None):
    """เขียน .fnt — line_height = ความสูงบรรทัด (ปกติ ascent + descent ของฟอนต์)"""
    assert len(glyphs) == NUM_GLYPHS
    if line_height is None:
        # ประมาณจาก glyph จริง: ascent สูงสุด + ส่วนที่ต่ำกว่า baseline ลึกสุด
        line_height = max((g.ascent for g in glyphs), default=0.0) + \
            max((g.px_height - g.ascent for g in glyphs), default=0.0)
    header = struct.pack("<fII", float(line_height), 1, 1)
    raw_name = name.encode("ascii")[:NAME_SIZE - 1] + b"\x00"
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
