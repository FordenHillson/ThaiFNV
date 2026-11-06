#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_builder.py — สร้างชุดฟอนต์ภาษาไทย Sarabun Bold 700 พร้อมเส้นขอบคมชัดและระยะช่องไฟพอดี

คุณสมบัติ:
  - ตัวหนังสือมีเส้นขอบคมชัด (Anti-Aliased Stroke) ไม่กลืนไปกับฉากหลัง
  - ปรับระยะ Advance ชดเชยความหนาของเส้นขอบ ป้องกันตัวอักษรเบียดทับกัน 100%
  - ปรับแต่งระดับความสูง (Ascent / Line Height) ให้อยู่กึ่งกลางกรอบตัวเลือกสีเหลืองของเมนูพอดี
  - จัดการสระบน/ล่าง/วรรณยุกต์ และ Precomposed Clusters (0x80-0x9B) อย่างประณีต
  - ตัวอักษรสีขาวบริสุทธิ์ใน Atlas เพื่อให้เอนจินของเกมคูณสี (Vertex Tint) ตามธีมสีส้มอำพันเดิม
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from fnt_lib import Glyph, save_fnt, save_tex
from thai_shaper_engine import (
    CLUSTER_TO_SLOT,
    LOW_TONE_MAP,
    CUT_DESCENDER_MAP,
    TALL_SPECIAL_MAP,
    SLOT_TALL_LOW_MAI_EK,
    SLOT_TALL_LOW_MAI_THO,
    SLOT_TALL_II_EK,
    SLOT_TALL_UEE_THO,
    SLOT_TALL_I,
    SLOT_TALL_II,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ASCII_RANGE = list(range(0x20, 0x7F))
COMBINING = set("ัิีึืฺุู็่้๊๋์ํ๎")
THAI_CONSONANTS = range(0xA1, 0xCF)

# ระยะชดเชยพิเศษสำหรับสระหน้า (ใ, ไ, โ, เ, แ) เพื่อป้องกันไม่ให้เส้นขอบชนเกยกับพยัญชนะที่ตามมา โดยไม่ห่างเกินไปจนเป็นช่องว่าง
LEADING_VOWELS_EXTRA = {
    'ใ': 0.8,
    'ไ': 0.8,
    'โ': 1.0,
    'เ': 0.5,
    'แ': 0.5,
}

# สีเส้นขอบ (โทนเข้ม-อบอุ่น เพื่อให้เมื่อคูณกับสีส้ม/ทองของเกมแล้วได้ขอบเข้มคมชัด ตัดกับแสงพื้นหลัง)
DEFAULT_OUTLINE_OUTER = (34, 26, 14)   # ขอบนอกเข้ม คมชัด
DEFAULT_OUTLINE_INNER = (115, 95, 55)  # ขอบในเชื่อมต่อเนียนตา


def round_adv(x: float) -> float:
    """ปัด advance เป็นจำนวนเต็ม เพื่อไม่ให้เกิด cumulative drift ในเอนจินเกม"""
    return float(math.floor(x + 0.5))


def get_ink_metrics(font: ImageFont.FreeTypeFont, ch: str, size: int, stroke: int = 0):
    """วัดกล่องหมึกจริง (ink box) จาก baseline"""
    pad = size * 3 + stroke + 4
    canvas = Image.new("L", (pad * 2, pad * 2), 0)
    ImageDraw.Draw(canvas).text((pad, pad), ch, font=font, anchor="ls", fill=255,
                                stroke_width=stroke, stroke_fill=255)
    bb = canvas.getbbox()
    if bb is None:
        return None
    l, t, r, b = bb[0] - pad, bb[1] - pad, bb[2] - pad, bb[3] - pad
    return l, t, max(1, r - l), max(1, b - t)


def draw_glyph_to_image(ch: str, font: ImageFont.FreeTypeFont, stroke: int = 0,
                        target_ascent: float | None = None,
                        outer_color=DEFAULT_OUTLINE_OUTER, inner_color=DEFAULT_OUTLINE_INNER):
    """วาด glyph หนึ่งตัวลงรูปภาพ พร้อมจัด baseline ให้ตรงกับ target_ascent เพื่อให้อยู่กึ่งกลางกรอบตัวเลือก"""
    raw = get_ink_metrics(font, ch, font.size, stroke=stroke)
    if raw is None:
        return None, 0, 0, 0, 0
    l, t, w, h = raw

    pad_x = stroke + 1
    natural_asc = stroke + 1 - t  # ระยะจากขอบบนกล่องหมึกถึง baseline

    # ถ้ามีการกำหนด target_ascent ให้ขยาย padding ด้านบนเพื่อให้ baseline อยู่ที่ target_ascent พอดี
    if target_ascent is not None and target_ascent > natural_asc:
        top_pad = int(round(target_ascent - natural_asc)) + pad_x
    else:
        top_pad = pad_x

    bot_pad = pad_x + 2

    img_w = w + pad_x * 2
    img_h = h + top_pad + bot_pad
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # พิกัด baseline ภายในภาพ
    draw_x = pad_x - l
    draw_y = top_pad - t

    # 1. วาดเส้นขอบนอก
    if stroke > 0:
        draw.text((draw_x, draw_y), ch, font=font, anchor="ls",
                  fill=(255, 255, 255, 255),
                  stroke_width=stroke, stroke_fill=outer_color + (255,))
        # 2. วาดเส้นขอบใน (ถ้า stroke >= 2)
        inner_w = stroke // 2
        if inner_w > 0 and inner_color is not None:
            draw.text((draw_x, draw_y), ch, font=font, anchor="ls",
                      fill=(255, 255, 255, 255),
                      stroke_width=inner_w, stroke_fill=inner_color + (255,))

    # 3. วาดตัวอักษรสีขาวบริสุทธิ์
    draw.text((draw_x, draw_y), ch, font=font, anchor="ls", fill=(255, 255, 255, 255))

    ascent = draw_y  # ระยะจากขอบบนภาพถึง baseline
    return img, img_w, img_h, ascent, l


def pack_rectangles(sizes: list[tuple[int, int, int]], max_side=2048):
    """Shelf packing จัด glyph ลงบน atlas สี่เหลี่ยมจัตุรัสแบบ 2^N"""
    order = sorted(sizes, key=lambda s: (-s[2], -s[1]))
    side = 256
    while side <= max_side:
        x, y = 1, 1
        shelf_h = 0
        placed = {}
        fits = True
        for key, w, h in order:
            if x + w + 1 > side:
                x = 1
                y += shelf_h + 1
                shelf_h = 0
            if y + h + 1 > side:
                fits = False
                break
            placed[key] = (x, y)
            x += w + 1
            if h > shelf_h:
                shelf_h = h
        if fits:
            return side, placed
        side *= 2
    raise RuntimeError(f"Atlas size exceeded {max_side}x{max_side}")


def build_font(ttf_path: str, name: str, size: int, out_base: str | None = None,
               line_height: float = 36.0, target_ascent: float | None = None, outline: int = 1,
               stroke_gap: float | None = None,
               tone_scale: float = 0.75,
               tone_clearance: float = 0.0):
    font = ImageFont.truetype(ttf_path, size)

    # หาความกว้างพยัญชนะไทยเฉลี่ย เพื่อใช้จัดกึ่งกลางสระบน/วรรณยุกต์
    cons_advs = []
    for code in THAI_CONSONANTS:
        try:
            ch = bytes([code]).decode("cp874")
            cons_advs.append(font.getlength(ch))
        except Exception:
            pass
    ref_cons_adv = (sum(cons_advs) / len(cons_advs)) if cons_advs else font.getlength("ก")

    # ระยะเว้นชดเชยเส้นขอบ (Advance Padding):
    # ป้องกันไม่ให้เส้นขอบที่บวมออกทางซ้ายและขวาชนเกยกันระหว่างตัวอักษร
    if stroke_gap is None:
        stroke_gap = float(outline * 2) + 1.2

    measured = {}

    # 1. วัด ASCII 0x20..0x7E
    for code in ASCII_RANGE:
        if code == 0x20:
            # Space
            sp_adv = round_adv(font.getlength(" ") + stroke_gap)
            measured[code] = {
                "img": None, "w": 0, "h": 0, "asc": 0,
                "bearing_x": 0.0, "advance": sp_adv, "combining": False,
            }
            continue

        ch = chr(code)
        img, w, h, asc, left_ink = draw_glyph_to_image(ch, font, stroke=outline, target_ascent=target_ascent)
        if img is None:
            continue
        adv = round_adv(font.getlength(ch) + stroke_gap)
        measured[code] = {
            "img": img, "w": w, "h": h, "asc": asc,
            "bearing_x": 0.0,
            "advance": adv,
            "combining": False,
        }

    # 2. วัดอักษรไทย 0xA1..0xFB
    for code in range(0xA1, 0xFC):
        try:
            ch = bytes([code]).decode("cp874")
        except Exception:
            continue

        is_combining = ch in COMBINING
        img, w, h, asc, left_ink = draw_glyph_to_image(ch, font, stroke=outline, target_ascent=target_ascent)
        if img is None:
            continue

        if is_combining:
            # สระบน/ล่าง/วรรณยุกต์เดี่ยว: จัดตำแหน่งกึ่งกลางพยัญชนะไทยเฉลี่ย (ref_cons_adv)
            # เพื่อให้เมื่อเอนจินวาดต่อจากพยัญชนะ ตัวสระ/วรรณยุกต์จะไม่เบี้ยวไปทางซ้ายหรือขวา
            pad_x = outline + 1
            mark_ink_w = float(w - pad_x * 2)
            if ch in "่้๊๋์":
                # วรรณยุกต์เดี่ยววางบนเสาขวาของพยัญชนะ (เยื้องขวาเล็กน้อย)
                bx = -round((ref_cons_adv + mark_ink_w) / 2.0 - 1.0)
            else:
                # สระบน (ิ, ี, ึ, ื, ั), ไม้ไต่คู้ (็), นิคหิต (ํ), สระล่าง (ุ, ู) จัดกึ่งกลางพยัญชนะพอดี
                bx = -round((ref_cons_adv + mark_ink_w) / 2.0)
            adv = -bx
        else:
            extra_lead = LEADING_VOWELS_EXTRA.get(ch, 0.0)
            adv = round_adv(font.getlength(ch) + stroke_gap + extra_lead)
            bx = 0.0

        measured[code] = {
            "img": img, "w": w, "h": h, "asc": asc,
            "bearing_x": float(bx),
            "advance": adv,
            "combining": is_combining,
        }

    # 3. Precomposed Glyphs 0x80..0x9B (สระบน + วรรณยุกต์ ซ้อน 2 ชั้น เช่น ตั้, นื้, ที่)
    # ตามหลัก Thai Typography: เมื่อวรรณยุกต์ซ้อนบนสระบน จะต้องย่อสัดส่วนวรรณยุกต์ลงเป็น ~80%
    # และยกขึ้น (lift) ให้พ้นจากยอดสระบน เพื่อไม่ให้เส้นขอบและตัวอักษรทับกันจนทึบหนา
    tone_size = max(10, int(round(size * tone_scale)))
    tone_font = ImageFont.truetype(ttf_path, tone_size)
    tone_stroke = max(1, outline // 2) if outline > 1 else outline

    for cluster, slot in CLUSTER_TO_SLOT.items():
        vowel, tone = cluster[0], cluster[1]
        mv = get_ink_metrics(font, vowel, size, stroke=outline)
        mt = get_ink_metrics(tone_font, tone, tone_size, stroke=tone_stroke)
        if mv is None or mt is None:
            continue

        vl, vt, vw, vh = mv
        tl, tt, tw, th = mt

        # ยกวรรณยุกต์ขึ้นให้แนบชิดกับไหล่ขวาของสระบน ไม่ลอยเคว้ง (ลด lift ลง 2.5px เพื่อให้กระชับสมดุลแบบ Google Docs)
        lift = int(round((tt + th) - vt - 2.5 + tone_clearance))
        tt_lifted = tt - lift

        left = min(vl, tl)
        top = min(vt, tt_lifted)
        right = max(vl + vw, tl + tw)
        bot = max(vt + vh, tt_lifted + th)

        pad_x = outline + 1
        natural_asc = pad_x - top
        if target_ascent is not None and target_ascent > natural_asc:
            top_pad = int(round(target_ascent - natural_asc)) + pad_x
        else:
            top_pad = pad_x

        img_w = (right - left) + pad_x * 2
        img_h = (bot - top) + top_pad + (pad_x + 2)
        img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        draw_x = pad_x - left
        draw_y = top_pad - top

        # วาดสระ
        if outline > 0:
            draw.text((draw_x, draw_y), vowel, font=font, anchor="ls", fill=(255, 255, 255, 255),
                      stroke_width=outline, stroke_fill=DEFAULT_OUTLINE_OUTER + (255,))
        draw.text((draw_x, draw_y), vowel, font=font, anchor="ls", fill=(255, 255, 255, 255))

        # วาดวรรณยุกต์ (ยกขึ้นเหนือสระบนด้วยขนาด 80% และเส้นขอบที่คมชัดไม่เกยกัน)
        if tone_stroke > 0:
            draw.text((draw_x, draw_y - lift), tone, font=tone_font, anchor="ls", fill=(255, 255, 255, 255),
                      stroke_width=tone_stroke, stroke_fill=DEFAULT_OUTLINE_OUTER + (255,))
        draw.text((draw_x, draw_y - lift), tone, font=tone_font, anchor="ls", fill=(255, 255, 255, 255))

        cluster_ink_w = float(right - left)
        # จัดตำแหน่งกึ่งกลางพยัญชนะไทยเฉลี่ย (ref_cons_adv) เพื่อไม่ให้สระ+วรรณยุกต์ซ้อนตกขอบซ้ายของพยัญชนะ
        bx = -round((ref_cons_adv + cluster_ink_w) / 2.0)
        measured[slot] = {
            "img": img, "w": img_w, "h": img_h, "asc": draw_y,
            "bearing_x": float(bx),
            "advance": -float(bx),
            "combining": True,
        }

    # 4. วรรณยุกต์ลดระดับ (0x9C..0x9F, 0xDB) สำหรับพยัญชนะที่ไม่มีสระบน (ค่า, ไม่, ถ้า, กอล์ฟ)
    for tone_ch, slot in LOW_TONE_MAP.items():
        img, w, h, asc, left_ink = draw_glyph_to_image(tone_ch, font, stroke=outline, target_ascent=target_ascent)
        if img is None:
            continue
        pad_x = outline + 1
        mark_ink_w = float(w - pad_x * 2)
        bx = -round((ref_cons_adv + mark_ink_w) / 2.0 - 1.0)
        measured[slot] = {
            "img": img, "w": w, "h": h, "asc": asc,
            "bearing_x": float(bx),
            "advance": -float(bx),
            "combining": True,
        }

    # 5. ญ และ ฐ ตัดเชิงล่าง (0xDC, 0xDD) สำหรับเวลาตามด้วย สระอุ, สระอู (ผู้หญิง, รัฐบาล)
    for base_ch, slot in CUT_DESCENDER_MAP.items():
        img, w, h, asc, left_ink = draw_glyph_to_image(base_ch, font, stroke=outline, target_ascent=target_ascent)
        if img is None:
            continue
        # ตัดหางด้านล่างออก (ส่วนที่ต่ำกว่า baseline)
        img_cut = img.copy()
        draw_cut = ImageDraw.Draw(img_cut)
        # baseline อยู่ที่ y = asc; ตัด pixels ด้านล่าง baseline
        cut_y = int(round(asc + max(1, outline)))
        draw_cut.rectangle([(0, cut_y), (w, h)], fill=(0, 0, 0, 0))
        adv = round_adv(font.getlength(base_ch) + stroke_gap)
        measured[slot] = {
            "img": img_cut, "w": w, "h": h, "asc": asc,
            "bearing_x": 0.0,
            "advance": adv,
            "combining": False,
        }

    # 6. Glyphs หลบหางพยัญชนะสูง ป, ฝ, ฟ (0xDE, 0xDF, 0xFC..0xFF)
    tall_shift = 3.0  # เลื่อนไปทางซ้าย 3px เพื่อหลบหาง
    # 6.1 วรรณยุกต์ต่ำเยื้องซ้าย (0xDE, 0xDF)
    for t_ch, slot in [('่', SLOT_TALL_LOW_MAI_EK), ('้', SLOT_TALL_LOW_MAI_THO)]:
        if slot in measured:
            continue
        img, w, h, asc, left_ink = draw_glyph_to_image(t_ch, font, stroke=outline, target_ascent=target_ascent)
        if img is None:
            continue
        pad_x = outline + 1
        mark_ink_w = float(w - pad_x * 2)
        bx = -round((ref_cons_adv + mark_ink_w) / 2.0 - 1.0) - tall_shift
        measured[slot] = {
            "img": img, "w": w, "h": h, "asc": asc,
            "bearing_x": float(bx),
            "advance": -float(bx),
            "combining": True,
        }

    # 6.2 สระบนเยื้องซ้าย (0xFE, 0xFF)
    for v_ch, slot in [('ิ', SLOT_TALL_I), ('ี', SLOT_TALL_II)]:
        img, w, h, asc, left_ink = draw_glyph_to_image(v_ch, font, stroke=outline, target_ascent=target_ascent)
        if img is None:
            continue
        pad_x = outline + 1
        mark_ink_w = float(w - pad_x * 2)
        bx = -round((ref_cons_adv + mark_ink_w) / 2.0) - tall_shift
        measured[slot] = {
            "img": img, "w": w, "h": h, "asc": asc,
            "bearing_x": float(bx),
            "advance": -float(bx),
            "combining": True,
        }

    # 6.3 สระ+วรรณยุกต์ซ้อนเยื้องซ้าย (0xFC, 0xFD)
    for cluster, slot in [("ี่", SLOT_TALL_II_EK), ("ื้", SLOT_TALL_UEE_THO)]:
        vowel, tone = cluster[0], cluster[1]
        mv = get_ink_metrics(font, vowel, size, stroke=outline)
        mt = get_ink_metrics(tone_font, tone, tone_size, stroke=tone_stroke)
        if mv is None or mt is None:
            continue
        vl, vt, vw, vh = mv
        tl, tt, tw, th = mt
        lift = int(round((tt + th) - vt - 2.5 + tone_clearance))
        tt_lifted = tt - lift
        left = min(vl, tl)
        top = min(vt, tt_lifted)
        right = max(vl + vw, tl + tw)
        bot = max(vt + vh, tt_lifted + th)
        pad_x = outline + 1
        natural_asc = pad_x - top
        top_pad = int(round(target_ascent - natural_asc)) + pad_x if target_ascent and target_ascent > natural_asc else pad_x
        img_w = (right - left) + pad_x * 2
        img_h = (bot - top) + top_pad + (pad_x + 2)
        img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw_x = pad_x - left
        draw_y = top_pad - top
        if outline > 0:
            draw.text((draw_x, draw_y), vowel, font=font, anchor="ls", fill=(255, 255, 255, 255),
                      stroke_width=outline, stroke_fill=DEFAULT_OUTLINE_OUTER + (255,))
        draw.text((draw_x, draw_y), vowel, font=font, anchor="ls", fill=(255, 255, 255, 255))
        if tone_stroke > 0:
            draw.text((draw_x, draw_y - lift), tone, font=tone_font, anchor="ls", fill=(255, 255, 255, 255),
                      stroke_width=tone_stroke, stroke_fill=DEFAULT_OUTLINE_OUTER + (255,))
        draw.text((draw_x, draw_y - lift), tone, font=tone_font, anchor="ls", fill=(255, 255, 255, 255))
        cluster_ink_w = float(right - left)
        bx = -round((ref_cons_adv + cluster_ink_w) / 2.0) - tall_shift
        measured[slot] = {
            "img": img, "w": img_w, "h": img_h, "asc": draw_y,
            "bearing_x": float(bx),
            "advance": -float(bx),
            "combining": True,
        }

    # 4. จัดวางภาพลง Atlas
    pack_items = [(code, m["w"], m["h"]) for code, m in measured.items() if m["img"] is not None]
    atlas_size, placements = pack_rectangles(pack_items)

    atlas = Image.new("RGBA", (atlas_size, atlas_size), (0, 0, 0, 0))
    glyphs = [Glyph() for _ in range(256)]

    inv = 1.0 / float(atlas_size)
    for code, m in measured.items():
        g = Glyph()
        if m["img"] is None:
            # Space
            g.px_width = 0.0
            g.px_height = 0.0
            g.bearing_x = 0.0
            g.advance_extra = m["advance"]
            g.ascent = 0.0
            glyphs[code] = g
            continue

        x, y = placements[code]
        w, h = m["w"], m["h"]
        atlas.paste(m["img"], (x, y))

        u1, v1 = x * inv, y * inv
        u2, v2 = (x + w) * inv, (y + h) * inv

        g.set_uv(u1, v1, u2, v2)
        g.px_width = float(w)
        g.px_height = float(h)
        g.bearing_x = m["bearing_x"]
        g.advance_extra = m["advance"] - float(w)
        g.ascent = float(m["asc"])
        glyphs[code] = g

    # บันทึกไฟล์ (ถ้ามี out_base)
    if out_base is not None:
        tex_path = out_base + ".tex"
        fnt_path = out_base + ".fnt"
        png_path = out_base + ".png"

        tex_name = os.path.basename(out_base)
        save_tex(tex_path, atlas.width, atlas.height, atlas.tobytes())
        save_fnt(fnt_path, tex_name, glyphs, line_height=line_height)
        atlas.save(png_path)
        print(f"ok: {out_base} (atlas {atlas_size}x{atlas_size}, line_h={line_height}, asc={target_ascent}, outline={outline})")

    return atlas, glyphs, line_height


# สล็อตมาตรฐานของ Fallout: New Vegas พร้อมค่า Line Height, Target Ascent, Outline, และ Stroke Gap
# จัดวางให้ตัวอักษรอยู่ "กึ่งกลางกรอบตัวเลือกสีเหลือง" พอดี และเรียงชิดสวยงามเป็นธรรมชาติเหมือน Google Docs
# (ชื่อไฟล์, ขนาด Sarabun, line_height, target_ascent, outline, stroke_gap)
VANILLA_SLOTS = [
    ("Baked-in_Monofonto_Large", 18, 38.0, 27.0, 2, 1.5),        # Slot 7: Start Menu (ขอบ 2px คมชัด, กึ่งกลางกรอบสมดุล)
    ("Glow_Monofonto_VL_dialogs", 18, 32.0, 23.0, 1, 0.5),       # Slot 6: Dialog / Settings (ชิดธรรมชาติเหมือน Google Docs)
    ("Monofonto_VeryLarge02_Dialogs2", 18, 36.0, 26.0, 1, 0.5),  # Slot 4: Version Info / HUD
    ("Glow_Monofonto_Large", 18, 31.0, 23.0, 1, 0.5),            # Slot 1: ข้อความป๊อปอัป
    ("Monofonto_Large", 17, 31.0, 23.0, 1, 0.5),                 # Slot 2: Stats / Map
    ("Glow_Monofonto_Medium", 15, 26.0, 19.0, 1, 0.5),           # Slot 3: Container / Loading
    ("Fixedsys_Comp_uniform_width", 20, 25.0, 19.0, 1, 0.5),     # Slot 5: Terminal
    ("Glow_Futura_Caps_Large", 36, 52.0, 38.0, 2, 1.5),          # Slot 8: หัวข้อใหญ่
    ("NVFont_Test", 26, 36.0, 27.0, 1, 0.5),                     # Slot 9: เทสต์
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttf", default=str(ROOT / "fonts" / "src" / "Sarabun-Bold.ttf"))
    ap.add_argument("--out-dir", default=str(ROOT / "fonts" / "out" / "vanilla"))
    ap.add_argument("--deploy", action="store_true", help="Deploy directly to game Data\\Textures\\Fonts")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    print(f"Building Sarabun Bold 700 with clear outline, natural spacing, and centered boxes...")
    for fname, size, lh, asc, otl, gap in VANILLA_SLOTS:
        out_base = os.path.join(args.out_dir, fname)
        build_font(args.ttf, fname, size, out_base, line_height=lh, target_ascent=asc, outline=otl, stroke_gap=gap)

    if args.deploy:
        game_fonts = Path(r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\Textures\Fonts")
        game_fonts.mkdir(parents=True, exist_ok=True)
        import shutil
        for fname, _, _, _, _, _ in VANILLA_SLOTS:
            for ext in (".fnt", ".tex", ".png"):
                src = Path(args.out_dir) / f"{fname}{ext}"
                if src.exists():
                    shutil.copy2(src, game_fonts / f"{fname}{ext}")
        print(f"Successfully deployed fonts -> {game_fonts}")


if __name__ == "__main__":
    main()
