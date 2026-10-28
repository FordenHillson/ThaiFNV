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
import unicodedata

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

    # NBSP (cp874 0xA0) ต้องเป็นช่องว่างกว้างเท่า space ไม่มีหมึก
    space_cp = 0x20
    space_adv = font.getlength(' ')

    def is_combining(ch):
        return unicodedata.combining(ch) > 0 or ch in COMBINING

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
    # vanilla ใช้ texture สี่เหลี่ยมจัตุรัสเสมอ (512², 420², 330² ...) — บังคับให้ตรงแบบ
    if tex_w != tex_h:
        sq = max(tex_w, tex_h)
        tex_w = tex_h = sq
    atlas = Image.new("RGBA", (tex_w, tex_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)

    glyphs = []
    for cp in range(256):
        g = Glyph()  # ช่องว่าง = ทุกค่า 0 (เหมือน vanilla) + f12=2.0
        g.y_offset = 2.0
        glyphs.append(g)

    x, y = margin, margin
    for idx, cp in enumerate(render_cps):
        if idx > 0 and (col := idx % cols) == 0:
            x = margin
            y += cell_h + margin
        ch = char_of[cp]
        bb = font.getbbox(ch)
        adv = advances[cp]
        combining = is_combining(ch)
        if ch == '\xa0':
            # NBSP: ไม่วาดหมึก — advance เท่า space
            adv = space_adv
            gw = space_adv
            glyphs[cp].advance = adv
            glyphs[cp].uv_left = glyphs[cp].uv_right = 0.0
            glyphs[cp].uv_top = glyphs[cp].uv_bottom = 0.0
            glyphs[cp].px_width = 0.0
            glyphs[cp].y_offset = 0.0
            x += cell_w + margin
            continue
        if combining:
            # สระบน/วรรณยุกต์ — advance = 0 (วาดทับใน cell เดียวกับตัวอักษรก่อนหน้า)
            adv = 0
            gw = max(bb[2] - bb[0], 2)
            if bb[0] < 0:
                gw = max(bb[2], 2)
        else:
            gw = max(bb[2], int(adv))
        # เว้นจุดวาดให้ top-left ของ glyph ไปในถูก cell
        draw.text((x, y - (bb[1] if bb[1] < 0 else 0)), ch, font=font,
                  fill=(255, 255, 255, 255))
        g = glyphs[cp]
        g.uv_left = x / tex_w
        g.uv_top = y / tex_h
        g.uv_right = (x + gw) / tex_w
        g.uv_bottom = (y + cell_h) / tex_h
        g.px_width = gw
        g.px_height = cell_h
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
    ap.add_argument("--name", default=None)
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--batch", default=None, help="ชื่อชุดใน FONTSETS: vanilla | darn")
    ap.add_argument("--out-dir", default=None, help="โฟลเดอร์ผลลัพธ์เมื่อใช้ --batch")
    args = ap.parse_args()
    if args.batch and (not args.out_dir):
        ap.error("--batch ต้องระบุ --out-dir ด้วย")

    if args.batch:
        os.makedirs(args.out_dir, exist_ok=True)
        for fname, size in FONTSETS[args.batch]:
            sub = argparse.Namespace(
                ttf=args.ttf, name=fname, size=size,
                out=os.path.join(args.out_dir, fname))
            print("--- %s (%dpx)" % (fname, size))
            build(sub)
        return

    build(args)


# ชุดไฟล์ที่ต้องมีในแพ็กเกจ — ชุดหลัก (vanilla slots) และ patch (DarNifiedUINV)
FONTSETS = {
    "vanilla": [
        ("Glow_Monofonto_Large", 20),
        ("Monofonto_Large", 20),
        ("Glow_Monofonto_Medium", 18),
        ("Monofonto_VeryLarge02_Dialogs2", 26),
        ("Fixedsys_Comp_uniform_width", 16),
        ("Glow_Monofonto_VL_dialogs", 22),
        ("Baked-in_Monofonto_Large", 20),
        ("Glow_Futura_Caps_Large", 24),
        ("NVFont_Test", 16),
    ],
    # DarN patch: ชื่อไฟล์ต้องตรง DarNifiedUINV เป๊ะ เพื่อ override ทับใน Data\Textures\Fonts
    "darn": [
        ("DarN_FranKleinBold_14", 14),
        ("DarN_FranKleinBold_16", 16),
        ("DarN_Libel_Suit_Otl_24", 24),
        ("DarN_Sui_Generis_Otl_10", 10),
        ("DarN_Sui_Generis_Otl_13", 13),
    ],
}


if __name__ == "__main__":
    main()
