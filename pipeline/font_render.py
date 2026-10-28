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
  python font_render.py --fnt ..\\fonts\\out\\vanilla\\Glow_Monofonto_Large.fnt ^
      --text "Continue\nการตั้งค่า" --color E0B93C --bg 1A140C --out ..\\testing\\render.png
"""
from __future__ import annotations
import argparse
import struct
import sys

from PIL import Image, ImageDraw

from fnt_lib import load_fnt, load_tex

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def render(fnt_path: str, text: str, scale: int = 2, pad: int = 8,
           color=None, bg=(20, 20, 24)):
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

    img = Image.new("RGBA", (max(canvas_w, 1), max(canvas_h, 1)), bg + (255,))
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
                if color is not None:
                    # เกมคูณสี vertex กับ RGB ใน texture
                    r, gg, bch, a = glyph_img.split()
                    r = r.point(lambda v: v * color[0] // 255)
                    gg = gg.point(lambda v: v * color[1] // 255)
                    bch = bch.point(lambda v: v * color[2] // 255)
                    glyph_img = Image.merge("RGBA", (r, gg, bch, a))
                img.alpha_composite(glyph_img, (round(pen + g.bearing_x),
                                                round(baseline - g.ascent)))
            pen += g.advance
        baseline += line_h

    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    return img


def parse_color(text: str):
    t = text.strip().lstrip("#")
    if len(t) != 6:
        raise SystemExit("--color ต้องเป็น hex 6 หลัก เช่น E0B93C")
    return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fnt", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--color", default=None, help="จำลอง tint ของเกม (hex)")
    ap.add_argument("--bg", default="141418", help="สีพื้นหลัง (hex)")
    args = ap.parse_args()
    color = parse_color(args.color) if args.color else None
    bg = parse_color(args.bg)
    img = render(args.fnt, args.text, args.scale, color=color, bg=bg)
    img.save(args.out)
    print("ok: %s (%dx%d)" % (args.out, img.width, img.height))


if __name__ == "__main__":
    main()
