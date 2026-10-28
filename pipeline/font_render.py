#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_render.py — จำลองการวาดข้อความแบบที่เกมทำ (ใช้ตรวจผลก่อนเข้าเกมจริง)

กฎเดียวกับ engine (ดู fnt_lib.py):
  pen_x, baseline เริ่มที่มุมซ้าย-บนของบรรทัด
  ต่อ 1 byte: b = ข้อความ[i]
      ถ้า glyph มีหมึก: วาดรูปจาก .tex ลงที่
          x = pen_x + bearing_x
          y = baseline - ascent
          ขนาด = px_width × px_height
      pen_x += advance   (advance = px_width + advance_extra)
  ขึ้นบรรทัดใหม่: baseline += line_height (header float)

Usage:
  python font_render.py --fnt ..\\fonts\\out\\Sarabun_20.fnt --text "ตัวอย่าง ข้อความ" --out ..\\testing\\render.png
"""
from __future__ import annotations
import argparse
import struct
import sys

from PIL import Image, ImageDraw

from fnt_lib import load_fnt, load_tex

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def render(fnt_path: str, text: str, scale: int = 2, pad: int = 8):
    name, glyphs = load_fnt(fnt_path)
    with open(fnt_path, "rb") as f:
        line_h = struct.unpack("<f", f.read(4))[0]
    w, h, rgba = load_tex(fnt_path[:-4] + ".tex")
    atlas = Image.frombytes("RGBA", (w, h), rgba)

    # วัดขนาดก่อน
    lines = text.split("\n")
    widths = []
    for line in lines:
        pen = 0.0
        for b in line.encode("cp874"):
            pen += glyphs[b].advance
        widths.append(pen)
    canvas_w = int(max(widths, default=1)) + pad * 2
    canvas_h = int(line_h * len(lines)) + pad * 2

    img = Image.new("RGBA", (max(canvas_w, 1), max(canvas_h, 1)), (20, 20, 24, 255))
    # engine วาง baseline ไว้ที่ขอบล่างของบรรทัด (glyph top = line_top + line_h - ascent)
    baseline = pad + line_h
    for line in lines:
        pen = 0.0
        for b in line.encode("cp874"):
            g = glyphs[b]
            if g.px_width > 0 and g.px_height > 0:
                box = (round(g.uv_left * w), round(g.uv_top * h),
                       round(g.uv_right * w), round(g.uv_bottom * h))
                glyph_img = atlas.crop(box)
                if glyph_img.size != (round(g.px_width), round(g.px_height)):
                    glyph_img = glyph_img.resize(
                        (max(1, round(g.px_width)), max(1, round(g.px_height))),
                        Image.LANCZOS)
                img.alpha_composite(glyph_img, (round(pen + g.bearing_x),
                                                round(baseline - g.ascent)))
            pen += g.advance
        baseline += line_h

    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fnt", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()
    img = render(args.fnt, args.text, args.scale)
    img.save(args.out)
    print("ok: %s (%dx%d)" % (args.out, img.width, img.height))


if __name__ == "__main__":
    main()
