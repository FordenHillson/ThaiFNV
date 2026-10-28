#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_patch.py — แพตช์บนไฟล์ vanilla จริง เติม glyph ไทย (CP874) แบบ minimal diff

วิธี:
  - ใช้ .fnt + .tex vanilla ต้นฉบับ (ของจริง) เป็นฐาน — glyph ASCII คงรูปเดิมทุกพิกเซล
  - ขยาย texture เป็นสี่เหลี่ยมจัตุรัสที่ใหญ่ขึ้น (วางของเดิมที่มุมบนซ้าย 1:1)
    แล้ว scale UV ของ glyph เดิมทั้งหมด → pixel ที่เกมสุ่มได้เหมือนเดิมเป๊ะ
  - เติม glyph ไทย (0xA0-0xFB) ลงในแถบว่างด้านล่าง พร้อม metric ที่ถูกต้อง
    (bearing X / ascent / advance วัดจาก baseline ของ TTF)
  - คง line height เดิมของ vanilla ไว้ (ไม่กระทบ layout ของ UI)

Usage:
  python font_patch.py --tex "..\\testing\\vanilla_bsa_fonts\\monofonto_large_0_lod_a.tex" ^
      --ttf ..\\fonts\\src\\Sarabun-Regular.ttf --out-dir ..\\fonts\\out\\patch
"""
from __future__ import annotations
import argparse
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

from fnt_lib import Glyph, load_fnt, load_tex, save_fnt, save_tex

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# สระบน/วรรณยุกต์/สระล่างไทย ที่ต้องไม่เลื่อน pen
COMBINING = set("ัิีึืฺุู็่้๊๋์ํ๎")
THAI_CONSONANTS = range(0xA1, 0xCF)
PAD = 1


def thai_char_of(cp: int):
    try:
        return bytes([cp]).decode("cp874")
    except UnicodeDecodeError:
        return None


def is_combining(ch: str) -> bool:
    return ch in COMBINING


def measure(font: ImageFont.FreeTypeFont, ch: str, size: int):
    """วัดกล่องหมึกจาก baseline → (left, top, width, height)"""
    pad = size * 3
    canvas = Image.new("L", (pad * 2, pad * 2), 0)
    ImageDraw.Draw(canvas).text((pad, pad), ch, font=font, anchor="ls", fill=255)
    bb = canvas.getbbox()
    if bb is None:
        return None
    l, t, r, b = bb[0] - pad, bb[1] - pad, bb[2] - pad, bb[3] - pad
    return l, t, max(1, r - l), max(1, b - t)


def fit_size_for_cap(ttf_path: str, cap_px: int) -> int:
    """เลือกขนาด TTF ให้ความสูงตัวพิมพ์ใหญ่ (H) ใกล้เคียง cap_px ของ vanilla"""
    probe = ImageFont.truetype(ttf_path, 100)
    m = measure(probe, "H", 100)
    cap100 = m[3] if m else 70
    return max(6, int(round(cap_px * 100.0 / cap100)))


def patch(fnt_path: str, tex_path: str, ttf_path: str, out_dir: str):
    line_h = None
    with open(fnt_path, "rb") as f:
        line_h = struct.unpack("<f", f.read(4))[0]
    _name, glyphs = load_fnt(fnt_path)
    w, h, rgba = load_tex(tex_path)
    vanilla = Image.frombytes("RGBA", (w, h), rgba)

    # ความสูงตัวพิมพ์ใหญ่ของ vanilla (อ้างอิงขนาดฟอนต์)
    cap_px = 0
    for cp in (0x48, 0x45, 0x41, 0x54):
        g = glyphs[cp]
        if g.px_height > 0:
            cap_px = int(round(g.px_height))
            break
    if cap_px <= 0:
        raise SystemExit("หา glyph ตัวพิมพ์ใหญ่ (H/E/A/T) ใน vanilla ไม่เจอ")

    size = fit_size_for_cap(ttf_path, cap_px)
    font = ImageFont.truetype(ttf_path, size)

    # เตรียม glyph ไทย
    items = []      # (cp, bearing, ascent, rw, rh, adv, l, t, ch)
    for cp in range(0xA0, 0x100):
        ch = thai_char_of(cp)
        if ch is None:
            continue
        m = measure(font, ch, size)
        if m is None:
            continue
        l, t, iw, ih = m
        items.append((cp, l - PAD, -t + PAD, iw + 2 * PAD, ih + 2 * PAD,
                      font.getlength(ch), l, t, ch))
    if not items:
        raise SystemExit("วัด glyph ไทยไม่ได้")

    cons = [font.getlength(thai_char_of(cp)) for cp in THAI_CONSONANTS
            if thai_char_of(cp)]
    cons = [a for a in cons if a > 0]
    ref_cons = sum(cons) / len(cons) if cons else 0.0

    # ขยาย atlas (สี่เหลี่ยมจัตุรัส) ให้มีแถบว่างด้านล่างพอ
    def place(side: int):
        """shelf packing ในแถบใต้ vanilla atlas → {cp: (x, y)} หรือ None"""
        x, y, shelf_h = 1, h + 1, 0
        out = {}
        for it in sorted(items, key=lambda v: -v[4]):
            cp, _b, _a, rw, rh = it[0], it[1], it[2], it[3], it[4]
            if x + rw + 1 > side:
                x, y, shelf_h = 1, y + shelf_h + 1, 0
            if y + rh + 1 > side:
                return None
            out[cp] = (x, y)
            x += rw + 1
            shelf_h = max(shelf_h, rh)
        return out

    side = max(w, h)
    placed = place(side)
    while placed is None:
        side *= 2
        placed = place(side)

    atlas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    atlas.paste(vanilla, (0, 0))
    draw = ImageDraw.Draw(atlas)

    # scale UV ของ glyph เดิม (pixel เดิมอยู่ตำแหน่งเดิม)
    sx, sy = w / side, h / side
    for g in glyphs:
        if g.px_width > 0 or g.px_height > 0:
            g.set_uv(g.uv_left * sx, g.uv_top * sy,
                     g.uv_right * sx, g.uv_bottom * sy)

    # วาง glyph ไทยในแถบด้านล่าง
    for cp, bearing, asc, rw, rh, adv, l, t, ch in items:
        x, y = placed[cp]
        draw.text((x + PAD - l, y + PAD - t), ch, font=font, anchor="ls",
                  fill=(255, 255, 255, 255))
        g = glyphs[cp]
        g.set_uv(x / side, y / side, (x + rw) / side, (y + rh) / side)
        g.px_width = rw
        g.px_height = rh
        g.ascent = asc
        if is_combining(ch):
            g.bearing_x = -(ref_cons + rw) / 2.0
            g.advance = 0
        else:
            g.bearing_x = bearing
            g.advance = adv

    name = os.path.basename(fnt_path)[:-4]
    os.makedirs(out_dir, exist_ok=True)
    save_fnt(os.path.join(out_dir, name + ".fnt"), name, glyphs, line_height=line_h)
    save_tex(os.path.join(out_dir, name + ".tex"), side, side, atlas.tobytes())
    atlas.save(os.path.join(out_dir, name + ".patched.png"))
    print("patched: %s (vanilla %dx%d -> %dx%d, cap=%dpx size=%dpx, line_h=%.0f, thai=%d)"
          % (name, w, h, side, side, cap_px, size, line_h, len(items)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", required=True, help="ไฟล์ .tex vanilla ต้นฉบับ")
    ap.add_argument("--fnt", default=None, help="ไฟล์ .fnt vanilla (default = ชื่อเดียวกัน)")
    ap.add_argument("--ttf", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    fnt = args.fnt or args.tex[:-4] + ".fnt"
    patch(fnt, args.tex, args.ttf, args.out_dir)


if __name__ == "__main__":
    main()
