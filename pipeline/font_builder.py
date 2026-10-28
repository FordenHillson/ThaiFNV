#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_builder.py — สร้างชุดฟอนต์ไทย (.fnt + .tex) จาก TTF (ThaiFNV pipeline)

หลักการ (ตรงกับรูปแบบ .fnt จริง — ดู fnt_lib.py):
  - เกมอ่านข้อความเป็น byte → ใช้ byte เป็น index ตาราง glyph 256 ช่อง
  - map ตาม CP874: 0x20-0x7E = ASCII, 0xA1-0xFB = ไทย (TIS-620)
  - แต่ละ glyph เก็บ "กล่องหมึก" (ink box) ของตัวเองเป็น quad:
        width/height = ขนาดกล่อง, bearing X = ระยะ pen→ขอบซ้าย,
        ascent = ระยะขอบบน→baseline (quad top = baseline - ascent),
        advance = width + advance_extra
  - สระบน/วรรณยุกต์ไทย (combining) = advance 0 + เลื่อนซ้ายไปทับพยัญชนะตัวก่อน
    (เกมไม่ทำ shaping เอง จึงต้อง encode ตำแหน่งไว้ใน bearing X)
  - header float = ความสูงบรรทัด (ascent + descent ของ TTF)
  - เส้นขอบ (outline): ฝังสีเข้มไว้ใน texture (เกมไม่มี outline ให้ font)
    เกมคูณสีจาก vertex (XML/SetTextColor) กับ RGB ใน texture → สีขอบจึงถูก
    คูณตามไปด้วย ต้องเลือกสีขอบเป็น "โทนกลาง-เข้ม" ไม่ใช่ดำสนิท
  - ตัวอักษรใน atlas เป็นสีขาว เพื่อให้ tint ของเกมคุมสีจริงได้

Usage:
   python font_builder.py --ttf ..\\fonts\\src\\Sarabun-Bold.ttf --batch vanilla --out-dir ..\\fonts\\out\\vanilla
   python font_builder.py --ttf ..\\fonts\\src\\Sarabun-Bold.ttf --batch darn --out-dir ..\\fonts\\out\\darn
   python font_builder.py --ttf ..\\fonts\\src\\Sarabun-Bold.ttf --name T --size 31 --out X --outline 2 --outline-color 6A5C40
"""
from __future__ import annotations
import argparse
import os
import sys
import unicodedata

from PIL import Image, ImageDraw, ImageFont

from fnt_lib import Glyph, save_fnt, save_tex

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ASCII ที่มีรูปจริง
ASCII_RANGE = list(range(0x20, 0x7F))
# สระบน/วรรณยุกต์/สระล่างไทย ที่ต้องไม่เลื่อน pen (combining)
COMBINING = set("ัิีึืฺุู็่้๊๋์ํ๎")
# ช่วงพยัญชนะไทย ใช้หาความกว้างอ้างอิงสำหรับวางสระ/วรรณยุกต์ให้อยู่กลางตัว
THAI_CONSONANTS = range(0xA1, 0xCF)
# สีเส้นขอบเริ่มต้น — ต้องเป็น "โทนกลาง" เพราะเกมคูณ tint ทับอีกชั้น
# (สีเข้มเกินจะกลายเป็นดำเมื่อคูณกับสีข้อความ)
DEFAULT_OUTLINE_COLOR = "6A5C40"
# สีเส้นใน (ระหว่างตัวอักษรกับขอบนอก) ให้ดูเป็นเส้นคู่แบบงานดีไซน์
DEFAULT_OUTLINE_INNER = "B0A078"


def auto_outline(size: int) -> int:
    """ความหนาเส้นขอบอัตโนมัติ: 1px ที่ตัวเล็ก, 2px ตั้งแต่ 20px ขึ้นไป"""
    return 1 if size < 20 else 2


def parse_color(text: str):
    t = text.strip().lstrip("#")
    if len(t) != 6:
        raise SystemExit("--outline-color ต้องเป็น hex 6 หลัก เช่น 4A3C16")
    return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))


def thai_char_of(cp: int):
    try:
        return bytes([cp]).decode("cp874")
    except UnicodeDecodeError:
        return None


def is_combining(ch: str) -> bool:
    return ch in COMBINING or unicodedata.combining(ch) > 0


def char_table() -> dict[int, str]:
    """byte → ตัวอักษร (ASCII ตรงตัว, ไทยผ่าน cp874)"""
    table = {cp: chr(cp) for cp in ASCII_RANGE}
    for cp in range(0xA0, 0x100):
        ch = thai_char_of(cp)
        if ch is not None:
            table[cp] = ch
    return table


def draw_glyph(draw, xy, ch, font, stroke=0, outer=(46, 36, 16), inner=None):
    """วาดตัวอักษรลง atlas: เส้นนอก → เส้นใน → ตัวอักษรสีขาว (ให้ tint เกมคุมสี)

    stroke คือความหนารวม (px) แบ่งครึ่ง: ครึ่งนอกเป็นสีเข้ม ครึ่งในเป็นสีอ่อน
    """
    if stroke > 0:
        draw.text(xy, ch, font=font, anchor="ls", fill=(255, 255, 255, 255),
                  stroke_width=stroke, stroke_fill=outer + (255,))
        inner_w = stroke // 2
        if inner is not None and inner_w > 0:
            draw.text(xy, ch, font=font, anchor="ls", fill=(255, 255, 255, 255),
                      stroke_width=inner_w, stroke_fill=inner + (255,))
    draw.text(xy, ch, font=font, anchor="ls", fill=(255, 255, 255, 255))


def ink_metrics(font: ImageFont.FreeTypeFont, ch: str, size: int, stroke: int = 0):
    """คืน (ink_left, ink_top, width, height) ของกล่องหมึก (ยังไม่รวม pad)

    วัดจาก baseline: ink_top ติดลบเมื่ออยู่เหนือ baseline, บวกเมื่ออยู่ใต้
    (ใช้การวาดจริงบน canvas เพราะ font.getbbox() คืนความสูงเกินจริงกับ
     glyph ที่ advance = 0 อย่างสระ/วรรณยุกต์ไทย)
    ถ้ามี stroke กล่องหมึกจะขยายตามความหนาเส้นขอบด้วย
    """
    pad = size * 3 + stroke + 2
    canvas = Image.new("L", (pad * 2, pad * 2), 0)
    ImageDraw.Draw(canvas).text((pad, pad), ch, font=font, anchor="ls", fill=255,
                                stroke_width=stroke, stroke_fill=255)
    bb = canvas.getbbox()
    if bb is None:
        return None
    l, t, r, b = bb[0] - pad, bb[1] - pad, bb[2] - pad, bb[3] - pad
    return l, t, max(1, r - l), max(1, b - t)


def pack_rects(sizes, max_side=2048):
    """shelf packing — sizes = [(key, w, h)] → (side, {key: (x, y)})"""
    order = sorted(sizes, key=lambda s: (-s[2], -s[1]))
    side = 256
    while side <= max_side:
        x = y = 1
        shelf_h = 0
        placed = {}
        fits = True
        for key, w, h in order:
            if w + 2 > side or h + 2 > side:
                fits = False
                break
            if x + w + 1 > side:
                x = 1
                y += shelf_h + 1
                shelf_h = 0
            placed[key] = (x, y)
            x += w + 1
            shelf_h = max(shelf_h, h)
        if fits and y + shelf_h + 1 <= side:
            return side, placed
        side *= 2
    raise SystemExit("atlas ใหญ่เกิน %dpx — ลดขนาดฟอนต์หรือจำนวน glyph" % max_side)


def build(args):
    font = ImageFont.truetype(args.ttf, args.size)
    ascent, descent = font.getmetrics()
    natural_h = ascent + descent
    # ความสูงบรรทัด: ใช้ค่าของ vanilla ตรง ๆ เพื่อไม่ให้กล่องข้อความเดิมล้น
    line_h = getattr(args, "line_height", None) or natural_h

    outline = getattr(args, "outline", None)
    if outline is None:
        outline = auto_outline(args.size)
    outline = max(0, int(round(outline)))
    outline_rgb = parse_color(getattr(args, "outline_color", DEFAULT_OUTLINE_COLOR))
    inner_hex = getattr(args, "outline_inner", DEFAULT_OUTLINE_INNER)
    if inner_hex and inner_hex.lower() in ("none", "-", "off", "0"):
        inner_hex = None
    inner_rgb = parse_color(inner_hex) if (inner_hex and outline > 0) else None
    pad = max(1, outline + 1)

    table = char_table()
    cps = sorted(table)

    # ความกว้างอ้างอิงของพยัญชนะไทย (สำหรับวางสระ/วรรณยุกต์ให้อยู่กลาง)
    cons_advs = [font.getlength(table[cp]) for cp in THAI_CONSONANTS if cp in table]
    cons_advs = [a for a in cons_advs if a > 0]
    ref_cons_adv = sum(cons_advs) / len(cons_advs) if cons_advs else 0.0

    # วัดกล่องหมึกทุก glyph → (bearing_x, ascent, rect_w, rect_h, advance, ink_left, ink_top)
    measured = {}
    for cp in cps:
        ch = table[cp]
        m = ink_metrics(font, ch, args.size, outline)
        if m is None:
            continue
        l, t, w, h = m
        measured[cp] = (l - pad, -t + pad, w + 2 * pad, h + 2 * pad,
                        font.getlength(ch), l, t)

    side, placed = pack_rects([(cp, m[2], m[3]) for cp, m in measured.items()])
    atlas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)

    glyphs = [Glyph() for _ in range(256)]

    for cp in cps:
        ch = table[cp]
        g = glyphs[cp]
        combining = is_combining(ch)
        if cp not in measured:
            # ไม่มีหมึก (space / NBSP / ตัวอักษรว่าง) — ใช้เฉพาะ advance
            g.advance = font.getlength(ch)
            continue
        bearing, asc, rw, rh, adv, ix, it = measured[cp]
        rx, ry = placed[cp]

        # วาดโดยให้ baseline/ขอบซ้ายของหมึกตรงกับตำแหน่งในกล่อง
        # ตัวอักษรเป็นสีขาว (เกมคูณ tint) ส่วนเส้นขอบฝังสีเข้มไว้ใน texture
        draw_glyph(draw, (rx + pad - ix, ry + pad - it), ch, font,
                   outline, outline_rgb, inner_rgb)

        g.set_uv(rx / side, ry / side, (rx + rw) / side, (ry + rh) / side)
        g.px_width = rw
        g.px_height = rh
        g.ascent = asc
        if combining:
            # ไม่เลื่อน pen และเลื่อนซ้ายไปกลางพยัญชนะตัวก่อนหน้า
            g.bearing_x = -(ref_cons_adv + rw) / 2.0
            g.advance = 0
        else:
            g.bearing_x = bearing
            # ไม่บวก advance: เมนูของเกมมีกรอบความกว้างจำกัด ถ้าข้อความกว้างขึ้น
            # จะถูกตัดขอบ (ทดสอบแล้วที่ advance + 2*stroke ข้อความถูก clip)
            g.advance = adv

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    save_fnt(args.out + ".fnt", args.name, glyphs, line_height=line_h)
    save_tex(args.out + ".tex", side, side, atlas.tobytes())
    atlas.save(args.out + ".png")
    print("ok: %s.fnt/.tex (atlas %dx%d, line_h=%d, glyphs=%d, outline=%d, ref_cons=%.1f)" %
          (args.out, side, side, line_h, len(measured), outline, ref_cons_adv))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttf", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--batch", default=None, help="ชื่อชุดใน FONTSETS: vanilla | darn")
    ap.add_argument("--out-dir", default=None, help="โฟลเดอร์ผลลัพธ์เมื่อใช้ --batch")
    ap.add_argument("--outline", type=float, default=None,
                    help="ความหนาเส้นขอบ (px) — ค่าเริ่มต้นคิดจากขนาดฟอนต์")
    ap.add_argument("--outline-color", default=DEFAULT_OUTLINE_COLOR,
                    help="สีเส้นขอบแบบ hex (ค่าเริ่มต้น %s)" % DEFAULT_OUTLINE_COLOR)
    ap.add_argument("--outline-inner", default=DEFAULT_OUTLINE_INNER,
                    help="สีเส้นในแบบ hex, ใส่ none เพื่อปิด (ค่าเริ่มต้น %s)"
                         % DEFAULT_OUTLINE_INNER)
    ap.add_argument("--line-height", type=float, default=None,
                    help="บังคับความสูงบรรทัด (ค่าเริ่มต้น ascent+descent)")
    args = ap.parse_args()
    if args.batch and (not args.out_dir):
        ap.error("--batch ต้องระบุ --out-dir ด้วย")
    if not args.batch:
        if not args.out:
            ap.error("ต้องระบุ --out หรือ --batch")
        if not args.name:
            args.name = os.path.basename(args.out)
        if not args.size:
            ap.error("ต้องระบุ --size")

    if args.batch:
        os.makedirs(args.out_dir, exist_ok=True)
        for fname, size, vanilla_lh in FONTSETS[args.batch]:
            sub = argparse.Namespace(
                ttf=args.ttf, name=fname, size=size,
                out=os.path.join(args.out_dir, fname),
                outline=args.outline, outline_color=args.outline_color,
                outline_inner=args.outline_inner,
                line_height=args.line_height or vanilla_lh)
            print("--- %s (%dpx)" % (fname, size))
            build(sub)
        return

    build(args)


# ชุดไฟล์ที่ต้องมีในแพ็กเกจ — ชุดหลัก (vanilla slots) และ patch (DarNifiedUINV)
#
# ขนาด px ต้อง "เทียบเท่าฟอนต์ vanilla" ไม่ใช่เดาจากชื่อไฟล์:
#   วัดจาก vanilla จริง (advance ตัวพิมพ์เล็กเฉลี่ย + ความสูงหมึกของ H)
#   แล้วเลือกขนาด Sarabun Bold ที่ให้ค่าใกล้เคียงที่สุด (ถ่วงน้ำหนักสองด้าน)
#   line_h = ความสูงบรรทัดของ vanilla (ใช้เป็นค่าต่ำสุด — ที่ต่ำกว่านี้สระไทยจะชนบรรทัดบน)
FONTSETS = {
    "vanilla": [
        # (ชื่อไฟล์, ขนาด Sarabun, line height ของ vanilla)
        ("Glow_Monofonto_Large", 31, 31),
        ("Monofonto_Large", 29, 31),
        ("Glow_Monofonto_Medium", 26, 26),
        ("Monofonto_VeryLarge02_Dialogs2", 40, 36),
        ("Fixedsys_Comp_uniform_width", 28, 25),
        ("Glow_Monofonto_VL_dialogs", 34, 34),
        ("Baked-in_Monofonto_Large", 31, 36),
        ("Glow_Futura_Caps_Large", 50, 52),
        ("NVFont_Test", 37, 36),
    ],
    # DarN patch: ชื่อไฟล์ต้องตรง DarNifiedUINV เป๊ะ เพื่อ override ทับใน Data\Textures\Fonts
    # (ชื่อ DarN มีขนาดอยู่ในชื่ออยู่แล้ว จึงใช้ขนาดตามชื่อ)
    "darn": [
        ("DarN_FranKleinBold_14", 14, None),
        ("DarN_FranKleinBold_16", 16, None),
        ("DarN_Libel_Suit_Otl_24", 24, None),
        ("DarN_Sui_Generis_Otl_10", 10, None),
        ("DarN_Sui_Generis_Otl_13", 13, None),
    ],
}

if __name__ == "__main__":
    main()
