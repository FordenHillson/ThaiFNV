#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_render.py — จำลองการวาดข้อความแบบ FalloutNV.exe (DrawGlyph 0xA142D0)

ยืนยันจาก RE (dump .text หลัง SteamStub):
  pen.x += bearing_x (+0x2C)
  วาด quad ที่ pen (y ≈ baseline - ascent; ascent = +0x34)
  pen.x += width (+0x24) + (width > 0 ? advance_extra (+0x30) : 0)

วัดความกว้างข้อความ (ฟังก์ชันวัดแยก): bearing + width + advance_extra เสมอ
(รวม space ที่ width=0 แต่ advance_extra > 0)

Usage:
  python font_render.py --fnt ..\\fonts\\out\\vanilla\\Glow_Monofonto_Large.fnt ^
      --text "Continue\\nการตั้งค่า" --color E0B93C --bg 1A140C --out ..\\testing\\render.png
"""
from __future__ import annotations
import argparse
import struct
import sys

from PIL import Image

from fnt_lib import Glyph, load_fnt, load_tex
from thai_precompose import encode_thai_cp874

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def measure_advance(g: Glyph) -> float:
    """ความกว้างต่อตัวตามเส้นวัดของเกม (ใช้ตอน wrap / จัด layout)"""
    return g.bearing_x + g.px_width + g.advance_extra


def draw_pen_delta(g: Glyph) -> float:
    """ระยะที่ pen เลื่อนสุทธิหลัง DrawGlyph หนึ่งตัว (รวม bearing ตอนต้น)"""
    extra = g.advance_extra if g.px_width > 0 else 0.0
    return g.bearing_x + g.px_width + extra


def measure_line(glyphs: list[Glyph], data: bytes) -> float:
    return sum(measure_advance(glyphs[b]) for b in data)


def wrap_lines(glyphs: list[Glyph], data: bytes, wrap_width: float) -> list[bytes]:
    """ตัดบรรทัดที่ช่องว่าง ASCII เมื่อความกว้าง (measure) เกิน wrap_width

    คล้ายเกม: หักที่ ' ' — ถ้าคำเดียวยาวเกินก็ปล่อยล้น
    """
    if wrap_width <= 0 or not data:
        return [data] if data else [b""]

    lines: list[bytes] = []
    # แยกตาม space แต่เก็บ space ไว้ท้ายโทเคน (ยกเว้นท้ายสุด)
    parts: list[bytes] = []
    cur = bytearray()
    for b in data:
        if b == 0x20:
            cur.append(b)
            parts.append(bytes(cur))
            cur = bytearray()
        else:
            cur.append(b)
    if cur:
        parts.append(bytes(cur))

    line = bytearray()
    line_w = 0.0
    for part in parts:
        pw = measure_line(glyphs, part)
        if line and line_w + pw > wrap_width:
            # ตัดก่อน part นี้ — ตัด space ท้ายบรรทัดเก่าถ้ามี
            while line and line[-1] == 0x20:
                line.pop()
            lines.append(bytes(line))
            line = bytearray(part.lstrip(b" "))
            line_w = measure_line(glyphs, bytes(line))
        else:
            line.extend(part)
            line_w += pw
    if line:
        while line and line[-1] == 0x20:
            line.pop()
        lines.append(bytes(line))
    return lines or [b""]


def render(fnt_path: str, text: str, scale: int = 2, pad: int = 8,
           color=None, bg=(20, 20, 24), precompose: bool = True,
           wrap_width: float = 0.0, encoded_lines: list[bytes] | None = None):
    """วาดข้อความ — ถ้าให้ encoded_lines จะข้าม encode จาก text"""
    _name, glyphs = load_fnt(fnt_path)
    with open(fnt_path, "rb") as f:
        line_h = struct.unpack("<f", f.read(4))[0]
    tex_w, tex_h, rgba = load_tex(fnt_path[:-4] + ".tex")
    atlas = Image.frombytes("RGBA", (tex_w, tex_h), rgba)

    def enc(line: str) -> bytes:
        return encode_thai_cp874(line) if precompose else line.encode("cp874", errors="replace")

    if encoded_lines is None:
        raw_lines = [enc(line) for line in text.split("\n")]
    else:
        raw_lines = list(encoded_lines)

    # wrap ต่อบรรทัดต้นทาง
    draw_lines: list[bytes] = []
    for raw in raw_lines:
        draw_lines.extend(wrap_lines(glyphs, raw, wrap_width))

    # ขอบเขตจริงหลัง DrawGlyph (รวม bearing ลบ)
    min_x = 0.0
    max_x = 1.0
    for ln in draw_lines:
        pen = 0.0
        for b in ln:
            g = glyphs[b]
            pen += g.bearing_x
            min_x = min(min_x, pen)
            if g.px_width > 0:
                max_x = max(max_x, pen + g.px_width)
            extra = g.advance_extra if g.px_width > 0 else 0.0
            pen += g.px_width + extra
            max_x = max(max_x, pen)
    origin_x = pad - min_x
    canvas_w = int(max_x - min_x) + pad * 2
    canvas_h = int(line_h * max(len(draw_lines), 1)) + pad * 2

    img = Image.new("RGBA", (max(canvas_w, 1), max(canvas_h, 1)), bg + (255,))
    baseline = pad + line_h
    for ln in draw_lines:
        pen = 0.0
        for b in ln:
            g = glyphs[b]
            # FNV DrawGlyph: เลื่อน bearing ก่อน แล้ววาดที่ pen
            pen += g.bearing_x
            if g.px_width > 0 and g.px_height > 0:
                box = (round(g.uv_left * tex_w), round(g.uv_top * tex_h),
                       round(g.uv_right * tex_w), round(g.uv_bottom * tex_h))
                glyph_img = atlas.crop(box)
                tw, th = max(1, round(g.px_width)), max(1, round(g.px_height))
                if glyph_img.size != (tw, th):
                    glyph_img = glyph_img.resize((tw, th), Image.LANCZOS)
                if color is not None:
                    r, gg, bch, a = glyph_img.split()
                    r = r.point(lambda v, c=color[0]: v * c // 255)
                    gg = gg.point(lambda v, c=color[1]: v * c // 255)
                    bch = bch.point(lambda v, c=color[2]: v * c // 255)
                    glyph_img = Image.merge("RGBA", (r, gg, bch, a))
                x = round(origin_x + pen)
                y = round(baseline - g.ascent)
                if 0 <= x < img.width and 0 <= y < img.height:
                    img.alpha_composite(glyph_img, (x, y))
            extra = g.advance_extra if g.px_width > 0 else 0.0
            pen += g.px_width + extra
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
    ap.add_argument("--wrap", type=float, default=0, help="ความกว้างตัดบรรทัด (px ฟอนต์)")
    ap.add_argument("--no-precompose", action="store_true",
                    help="encode CP874 ดิบ (ไม่รวมสระบน+วรรณยุกต์)")
    args = ap.parse_args()
    color = parse_color(args.color) if args.color else None
    bg = parse_color(args.bg)
    img = render(args.fnt, args.text, args.scale, color=color, bg=bg,
                 precompose=not args.no_precompose, wrap_width=args.wrap)
    img.save(args.out)
    print("ok: %s (%dx%d)" % (args.out, img.width, img.height))


if __name__ == "__main__":
    main()
