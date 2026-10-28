#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_builder.py — สร้างชุดฟอนต์ไทย (.fnt + .tex) จาก TTF (ThaiFNV prototype)

ตรรกะของ builder (ตามสมมติฐาน H1):
  - เกมอ่านข้อความเป็น bytes → ใช้ byte เดิมเป็น index ตาราง glyph 256 ตัว
  - เรา map ตาม CP874: byte 0x20-0x7E = ASCII, 0xA0-0xDB = ไทย (TIS-620 ไตอสมือ)
  - แยกแยะ: ศระ/วนรณยุกต (combine) = advance 0 + y_offset (เขียนทับลง cell ก่อน)

ชุด glyph ที่สร้าง: ทุกตัวอักษรในตาราง ASCII + ไทยตาม CP874 ถว่างช่องทุกตัวอื่นเป็นว่าง (แบบ vanilla)

Usage:
   python font_builder.py --ttf ..\\fonts\\src\\Sarabun-Regular.ttf --name Sarabun_16 --size 16 --out ..\\fonts\\out\\Sarabun_16
"""
from __future__ import annotations
import argparse
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

from fnt_lib import Glyph, save_fnt, save_tex

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ASCII ที่มีรูปจริงในหน้า printing charset
ASCII_RANGE = list(range(0x20, 0x7F))
# CP874/TIS-620 ไทย (ยงอายุ ทุกช่องที่มี aquam anus)
THAI_RANGE = [c for c in range(0xA0, 0xFF) if bytes([c]).decode("cp874", "ignore")]
# สระบน + วรรณยุกต์ (zero advance รายเชิญเรียง) — จาก Unicode block Thai
COMBINING = set("ัํ็่้๊๋์ํ๎")


def build(args):
    font = ImageFont.truetype(args.ttf, args.size)
    ascent, descent = font.getmetrics()
    cell_h = ascent + descent

    # ช่อง glyph ที่มีรูปจริง: ASCII + ไทยตาม CP874
    # map byte → อักษร: ASCII ใช้ chr(), ไทยต้อง decode ผ่าน cp874 เท่านั้น
    char_of = {cp: chr(cp) for cp in ASCII_RANGE}
    thai_chars = {}
    for cp in range(0xA0, 0x100):
        try:
            ch = bytes([cp]).decode("cp874")
        except UnicodeDecodeError:
            continue
        thai_chars[cp] = ch
    char_of.update(thai_chars)
    render_cps = sorted(char_of)
    advances = {cp: font.getlength(char_of[cp]) for cp in render_cps}
    thai_cp_set = set(thai_chars)

    # shelf packing บน atlas
    margin = 2
    cell_w = int(max(max(font.getlength(chr(cp)) for cp in render_cps) + 4, 16))
    n = len(render_cps)
    cols = max(1, min(n, 32))
    rows = -(-n // cols)
    w = cols * (cell_w + margin) + margin
    h = rows * (cell_h + margin) + margin
    tex_w = 1 << (w - 1).bit_length()
    tex_h = 1 << (h - 1).bit_length()
    atlas = Image.new("RGBA", (tex_w, tex_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)

    glyphs = []
    for cp in range(256):
        g = Glyph()
        g.px_height = cell_h
        g.y_offset = 2.0  # ช่องว่าง: dummy เหมือน vanilla (f12=2.0, advance=0)
        glyphs.append(g)

    x, y = margin, margin
    for idx, cp in enumerate(render_cps):
        if idx > 0 and (col := idx % cols) == 0:
            x = margin
            y += cell_h + margin
        ch = char_of[cp]
        bb = font.getbbox(ch)
        adv = advances[cp]
        if adv <= 0 or ch in COMBINING:
            # สระบน/วรรณยุกต์ — วาดเพื่อเป็นรูป แต่ advance = 0
            adv = 0
            gw = max(bb[2] - bb[0], 1)
        else:
            gw = max(bb[2], int(adv))
            if cp not in thai_cp_set and ch.isascii():
                pass
        # เว้นจุดวาดให้ top-left ของ glyph ไปในถูก cell
        draw.text((x, y - (bb[1] if bb[1] < 0 else 0)), ch, font=font,
                  fill=(255, 255, 255, 255))
        g = glyphs[cp]
        g.uv_left = x / tex_w
        g.uv_top = y / tex_h
        g.uv_right = (x + gw) / tex_w
        g.uv_bottom = (y + cell_h) / tex_h
        g.px_width = gw
        g.advance = adv
        g.x_offset = 0
        g.y_offset = 0
        x += cell_w + margin

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    save_fnt(args.out + ".fnt", args.name, glyphs)
    save_tex(args.out + ".tex", tex_w, tex_h, atlas.tobytes())
    atlas.save(args.out + ".png")
    print("ok: %s.fnt/.tex (atlas %dx%d, cell_h=%d, glyph columns=%d rows=%d)" %
          (args.out, tex_w, tex_h, cell_h, cols, rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttf", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    build(args)


if __name__ == "__main__":
    main()
