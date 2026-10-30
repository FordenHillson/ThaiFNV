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
import math
import os
import sys
import unicodedata

from PIL import Image, ImageDraw, ImageFont

from fnt_lib import Glyph, save_fnt, save_tex
from thai_precompose import PRECOMPOSE_TABLE

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
DEFAULT_OUTLINE_COLOR = "6A5C40"  # โทนกลาง — คูณ tint ทองแล้วได้ขอบเข้มพอดี (ดู docs)
# สีเส้นใน (ระหว่างตัวอักษรกับขอบนอก) ให้ดูเป็นเส้นคู่แบบงานดีไซน์
DEFAULT_OUTLINE_INNER = "B0A078"


def auto_outline(size: int) -> int:
    """ความหนาเส้นขอบ — เกมใช้ความสูง glyph จัด UI; outline≥2 ที่เมนู/กล่องข้อความจะดันล้นกรอบ
    จึงใช้ 1px เป็นหลัก (FreeType stroke เนียน) และ 2px เฉพาะหัวข้อใหญ่
    """
    return 1 if size < 36 else 2


def auto_tracking(size: int) -> float:
    """ระยะห่างระหว่างตัวอักษร (px) — ประมาณ 8% ของขนาดฟอนต์

    เกมไม่ทำ kerning/tracking ให้ จึงต้องเผื่อไว้ใน advance เอง
    (ค่ามากเกินจะทำให้ข้อความในเมนูถูกตัดขอบ — ดู docs)
    """
    return max(1.0, round(size * 0.08, 1))


def round_adv(x: float) -> float:
    """ปัด advance เป็นจำนวนเต็ม px (ปัดครึ่งขึ้น)

    เกมคำนวณความกว้างข้อความสำหรับ justify ด้วย advance แบบจำนวนเต็ม
    (vanilla ทุกไฟล์ advance เป็น int) แต่ตอนวาดใช้ค่าทศนิยมเต็ม
    ถ้า advance มีเศษ ข้อความยาวจะเยื้องขวาสะสม ~0.4px/ตัวอักษร
    """
    return float(math.floor(x + 0.5))


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

    ใช้ FreeType stroke (anti-alias) — ขอบเนียน ไม่แตกแบบ hard-mask
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

    tracking = getattr(args, "tracking", None)
    if tracking is None:
        tracking = auto_tracking(args.size)
    tracking = float(tracking)
    # ช่องว่างแนวนอนพิเศษหลังทุก glyph (px) — แยกจาก tracking ใน advance ของ TTF
    letter_gap = float(getattr(args, "letter_gap", 0) or 0)

    # ระยะบรรทัดใน UI หลายจุดใช้ metrics ของ glyph ไม่ใช่แค่ header float
    # (วัด 2026-10-30: ขยาย line_h header / pad เฉพาะ ASCII แล้วยังทับใน MessageMenu)
    metric_pad_top = int(getattr(args, "metric_pad_top", 0) or 0)
    metric_pad_bot = int(getattr(args, "metric_pad_bot", 0) or 0)
    # สระบน/วรรณยุกต์: ยกขึ้นให้พ้น outline ของพยัญชนะ
    upper_mark_lift = int(getattr(args, "upper_mark_lift", 0) or 0)
    # สมมติฐาน H: MessageMenu ใช้ max(px_height) ของตัวในบรรทัดเป็นระยะบรรทัด
    # สตริงไทยล้วน max_h≈25 แต่ max_asc+max_desc≈31 → gap ติดลบ → บังคับสูงขั้นต่ำ
    min_glyph_h = int(getattr(args, "min_glyph_height", 0) or 0)
    min_below = int(getattr(args, "min_below", 0) or 0)

    table = char_table()
    cps = sorted(table)

    # ความกว้างอ้างอิงของพยัญชนะไทย (สำหรับวางสระ/วรรณยุกต์ให้อยู่กลาง)
    cons_advs = [font.getlength(table[cp]) for cp in THAI_CONSONANTS if cp in table]
    cons_advs = [a for a in cons_advs if a > 0]
    ref_cons_adv = sum(cons_advs) / len(cons_advs) if cons_advs else 0.0

    # สระบน (ชั้นใกล้พยัญชนะ) vs วรรณยุกต์ (ชั้นสูงกว่า) — ต้องแยก ascent
    # ไม่งั้น ที่ / ชิ้น จะทับกันเอง (วัด: ี asc≈19 กับ ่ asc≈18 เกือบเท่า)
    UPPER_VOWELS = set("ัิีึื็ํ")
    TONE_MARKS = set("่้๊๋์๎")
    UPPER_MARKS = UPPER_VOWELS | TONE_MARKS
    # วรรณยุกต์ยกสูงกว่าสระบนเสมอ (แม้ --upper-mark-lift=0)
    # ระยะแนวตั้งระหว่างสระบนกับวรรณยุกต์ (ที่/ชิ้น ต้องเห็นแยกชั้น)
    tone_extra_lift = max(8, int(round(args.size * 0.45)))

    # วัดกล่องหมึกทุก glyph → dict ต่อ codepoint
    #
    # สระ/วรรณยุกต์: ไม่ใส่ outline — กล่องมาร์คที่หนาเท่าพยัญชนะทำให้ยื่นทับตัวถัดไป
    measured = {}
    for cp in cps:
        ch = table[cp]
        combining = is_combining(ch)
        g_outline = 0 if combining else outline
        g_pad = 1 if combining else pad
        m = ink_metrics(font, ch, args.size, g_outline)
        if m is None:
            continue
        l, t, w, h = m
        lift = 0
        if combining and ch in UPPER_MARKS:
            lift = upper_mark_lift
            if ch in TONE_MARKS:
                lift += tone_extra_lift
            if lift > 0:
                t = t - lift
                h = h + lift
        # metric pad + min height: เฉพาะตัวฐาน (ไม่ใช่ combining)
        mpt = 0 if combining else metric_pad_top
        mpb = 0 if combining else metric_pad_bot
        asc = -t + g_pad + mpt
        rh = h + 2 * g_pad + mpt + mpb
        if not combining:
            if min_below > 0 and rh < asc + min_below:
                rh = asc + min_below
            if min_glyph_h > 0 and rh < min_glyph_h:
                extra = min_glyph_h - rh
                asc += extra
                rh += extra
                mpt += extra
            # ห้ามขยายทุก glyph ให้สูง = line_h — เกมใช้ความสูง glyph จริงจัดตำแหน่ง UI
            # (พองแล้วปุ่ม Yes/Continue หลุดล่างกรอบ; minh≈48 ก็เคยดันเมนูหาย)
            # เปิดได้ด้วย --match-line-height ถ้าต้องการทดลอง
            if getattr(args, "match_line_height", False) and line_h > rh + 0.5:
                deficit = int(round(line_h - rh))
                if deficit > 0:
                    rh += deficit
                    mpb += deficit
        measured[cp] = {
            "combining": combining,
            "outline": g_outline,
            "pad": g_pad,
            "mpt": mpt,
            "asc": asc,
            "rw": w + 2 * g_pad,
            "rh": rh,
            "adv": font.getlength(ch),
            "iw": w,
            "ix": l,
            "it": t,
            "lift": lift,
            "precompose": None,
        }

    # Precompose สระบน+วรรณยุกต์ → ช่อง 0x80–0x9B (ชั้น 3: ที่/ชิ้น/เปลี่ยน)
    for cluster, slot in PRECOMPOSE_TABLE.items():
        vowel, tone = cluster[0], cluster[1]
        mv = ink_metrics(font, vowel, args.size, 0)
        mt = ink_metrics(font, tone, args.size, 0)
        if mv is None or mt is None:
            continue
        vl, vt, vw, vh = mv
        tl, tt, tw, th = mt
        # ยกวรรณยุกต์เหนือสระบน
        tt_lifted = tt - tone_extra_lift
        th_lifted = th + tone_extra_lift
        # รวมกล่อง
        left = min(vl, tl)
        top = min(vt, tt_lifted)
        right = max(vl + vw, tl + tw)
        bot = max(vt + vh, tt_lifted + th_lifted)
        g_pad = 1
        w = max(1, right - left)
        h = max(1, bot - top)
        measured[slot] = {
            "combining": True,
            "outline": 0,
            "pad": g_pad,
            "mpt": 0,
            "asc": -top + g_pad,
            "rw": w + 2 * g_pad,
            "rh": h + 2 * g_pad,
            "adv": 0.0,
            "iw": w,
            "ix": left,
            "it": top,
            "lift": tone_extra_lift,
            "precompose": {
                "vowel": vowel, "tone": tone,
                "vl": vl, "vt": vt,
                "tl": tl, "tt": tt_lifted,
            },
        }

    cons_rws = [measured[cp]["rw"] for cp in THAI_CONSONANTS if cp in measured]
    ref_cons_rw = sum(cons_rws) / len(cons_rws) if cons_rws else ref_cons_adv
    # ความกว้างเซลล์สระบน (หลังได้ rw) — วรรณยุกต์จะดึงกลับมายังเซลล์นี้แล้วซ้อนแนวตั้ง
    upper_rws = [measured[cp]["rw"] for cp in cps
                 if cp in measured and table[cp] in UPPER_VOWELS]
    ref_upper_w = sum(upper_rws) / len(upper_rws) if upper_rws else 12.0

    side, placed = pack_rects([(cp, m["rw"], m["rh"]) for cp, m in measured.items()])
    atlas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)

    glyphs = [Glyph() for _ in range(256)]
    # #region agent log
    _dbg_marks = []
    # #endregion

    draw_cps = sorted(measured.keys())
    for cp in draw_cps:
        g = glyphs[cp]
        m = measured[cp]
        combining = m["combining"]
        g_pad = m["pad"]
        g_outline = m["outline"]
        iw, ix, it = m["iw"], m["ix"], m["it"]
        rw, rh, adv = m["rw"], m["rh"], m["adv"]
        rx, ry = placed[cp]
        pc = m.get("precompose")

        if pc:
            # origin เดียวกับ glyph ปกติ: หมึก (ix,it) ไปที่มุมบนซ้ายของเซลล์+pad
            # สระ/วรรณยุกต์ใช้ origin เดียวกัน → ซ้อนตามตำแหน่งฟอนต์จริง
            # วรรณยุกต์ยกเพิ่ม tone_extra_lift (tt ใน pc ถูกเลื่อนแล้วตอนวัด)
            ox = rx + g_pad - ix
            oy = ry + g_pad - it
            lift = m.get("lift") or 0
            draw_glyph(draw, (ox, oy), pc["vowel"], font, 0, outline_rgb, None)
            draw_glyph(draw, (ox, oy - lift), pc["tone"], font, 0, outline_rgb, None)
            ch_label = pc["vowel"] + pc["tone"]
        else:
            ch = table[cp]
            draw_glyph(draw, (rx + g_pad - ix, ry + g_pad + m["mpt"] - it), ch, font,
                       g_outline, outline_rgb, inner_rgb if g_outline > 0 else None)
            ch_label = ch

        g.set_uv(rx / side, ry / side, (rx + rw) / side, (ry + rh) / side)
        g.px_width = rw
        g.px_height = rh
        g.ascent = m["asc"]
        if combining:
            # แบบ FNVThai: bear=-w, adv=w (รวม precompose ชั้น 3)
            g.bearing_x = -float(rw)
            g.advance = round_adv(max(rw, 1.0))
            # #region agent log
            _dbg_marks.append({
                "cp": "0x%02X" % cp, "ch": ch_label, "w": rw, "iw": iw,
                "pad": g_pad, "bearing": round(g.bearing_x, 2),
                "adv": g.advance, "asc": round(g.ascent, 2),
                "lift": m["lift"], "pre": bool(pc),
            })
            # #endregion
        else:
            # ช่องว่างแนวนอนคงที่: advance = ความกว้างหมึกจริง + tracking + gap
            g.bearing_x = 0.0
            ink_w = max(adv, float(iw))
            g.advance = round_adv(ink_w + tracking + letter_gap)

    # space / ช่องว่างที่ไม่มีหมึก
    for cp in cps:
        if cp in measured:
            continue
        ch = table[cp]
        glyphs[cp].advance = round_adv(font.getlength(ch) + tracking)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    save_fnt(args.out + ".fnt", args.name, glyphs, line_height=line_h)
    save_tex(args.out + ".tex", side, side, atlas.tobytes())
    try:
        atlas.save(args.out + ".png")
    except OSError as e:
        # PNG เป็นแค่พรีวิว — อย่าให้ AV/Vortex ล็อกแล้วพังทั้งชุด
        print("warn: บันทึก PNG ไม่ได้ (%s) — ข้าม" % e)
    # #region agent log
    try:
        import json, time
        _log = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", ".cursor", "debug-8f0ee2.log")
        os.makedirs(os.path.dirname(os.path.abspath(_log)), exist_ok=True)
        with open(_log, "a", encoding="utf-8") as _f:
            _f.write(json.dumps({
                "sessionId": "8f0ee2", "runId": "post-fix", "hypothesisId": "E",
                "location": "font_builder.py:build",
                "message": "combining marks after rebuild",
                "data": {"font": args.name, "size": args.size, "marks": _dbg_marks[:8],
                         "mark_count": len(_dbg_marks)},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    # #region agent log
    try:
        import json, time
        _H = glyphs[ord("H")]
        _thai = [glyphs[c] for c in range(0xA0, 0x100) if glyphs[c].px_width > 0]
        _tmax_h = max((g.px_height for g in _thai), default=0)
        _tmax_a = max((g.ascent for g in _thai), default=0)
        _tmax_d = max((g.px_height - g.ascent for g in _thai), default=0)
        _log = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", ".cursor", "debug-8f0ee2.log")
        with open(_log, "a", encoding="utf-8") as _f:
            _f.write(json.dumps({
                "sessionId": "8f0ee2", "runId": "min-glyph-h", "hypothesisId": "H",
                "location": "font_builder.py:build",
                "message": "Thai max_h vs span after min_glyph_height",
                "data": {
                    "font": args.name, "line_h": line_h, "tracking": tracking,
                    "min_glyph_h": min_glyph_h, "min_below": min_below,
                    "metric_pad_top": metric_pad_top, "metric_pad_bot": metric_pad_bot,
                    "upper_mark_lift": upper_mark_lift,
                    "H_asc": _H.ascent, "H_h": _H.px_height,
                    "thai_max_h": _tmax_h, "thai_max_asc": _tmax_a,
                    "thai_max_desc": _tmax_d,
                    "gap_if_LH_max_h": round(_tmax_h - _tmax_a - _tmax_d, 2),
                    "mark_sample": _dbg_marks[:4],
                },
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
        # #region agent log
        # สมมติฐาน I: spacing พังเพราะ minh ไปขยาย combining — ตรวจว่ามาร์คกลับเป็น ink-tight
        _mark_hs = [m["w"] for m in _dbg_marks]  # placeholder
        _imai = glyphs[0xD4]  # ิ
        _mai = glyphs[0xE8]   # ่
        with open(_log, "a", encoding="utf-8") as _f:
            _f.write(json.dumps({
                "sessionId": "8f0ee2", "runId": "spacing-fix", "hypothesisId": "I",
                "location": "font_builder.py:build",
                "message": "combining mark quads after skip-minh",
                "data": {
                    "font": args.name,
                    "sara_i": {"w": _imai.px_width, "h": _imai.px_height,
                               "asc": _imai.ascent, "bear": round(_imai.bearing_x, 2),
                               "adv": _imai.advance},
                    "mai_ek": {"w": _mai.px_width, "h": _mai.px_height,
                               "asc": _mai.ascent, "bear": round(_mai.bearing_x, 2),
                               "adv": _mai.advance},
                    "cons_ko": {"w": glyphs[0xA1].px_width, "h": glyphs[0xA1].px_height,
                                "asc": glyphs[0xA1].ascent, "adv": glyphs[0xA1].advance},
                    "marks_not_inflated": (_imai.px_height < 30 and _mai.px_height < 30),
                },
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
        # #endregion
    except Exception:
        pass
    # #endregion
    print("ok: %s.fnt/.tex (atlas %dx%d, line_h=%d, glyphs=%d, outline=%d, "
          "tracking=%.1f, gap=%.1f, ref_cons=%.1f, mpad=%d+%d, lift=%d, minh=%d)" %
          (args.out, side, side, line_h, len(measured), outline, tracking,
           letter_gap, ref_cons_adv, metric_pad_top, metric_pad_bot,
           upper_mark_lift, min_glyph_h))


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
    ap.add_argument("--match-line-height", action="store_true",
                    help="ขยายกล่อง glyph ให้สูงเท่า line_h (เติมล่าง) — ปิดเป็นค่าเริ่มต้น เพราะดันข้อความหลุดกรอบ UI")
    ap.add_argument("--no-match-line-height", action="store_true",
                    help=argparse.SUPPRESS)  # เดิม; ค่าเริ่มต้นคือไม่ขยายแล้ว
    ap.add_argument("--tracking", type=float, default=None,
                    help="ระยะห่างระหว่างตัวอักษร (px) — ค่าเริ่มต้นคิดจากขนาดฟอนต์")
    ap.add_argument("--letter-gap", type=float, default=None,
                    help="ช่องว่างแนวนอนพิเศษหลังทุก glyph (px)")
    ap.add_argument("--metric-pad-top", type=int, default=None,
                    help="เติมช่องว่างบน glyph เพื่อขยายระยะบรรทัด (UI อ่าน metrics)")
    ap.add_argument("--metric-pad-bot", type=int, default=None,
                    help="เติมช่องว่างล่าง glyph เพื่อขยายระยะบรรทัด")
    ap.add_argument("--upper-mark-lift", type=int, default=None,
                    help="ยกสระบน/วรรณยุกต์ขึ้น (px) ให้พ้นพยัญชนะ")
    ap.add_argument("--min-glyph-height", type=int, default=None,
                    help="บังคับความสูง glyph ขั้นต่ำ (px) — กัน LH=max(h) ติดลบ")
    ap.add_argument("--min-below", type=int, default=None,
                    help="บังคับให้ quad ยื่นต่ำกว่า baseline อย่างน้อย N px")
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
        for entry in FONTSETS[args.batch]:
            fname, size, vanilla_lh = entry[:3]
            tracking_pct = entry[3] if len(entry) > 3 else None
            tracking = args.tracking
            if tracking is None and tracking_pct is not None:
                tracking = round(size * tracking_pct, 1)
            # ค่าเริ่มต้นสำหรับชุด vanilla: บังคับสูง glyph ให้พอสำหรับไทยหลายบรรทัด
            mpt = args.metric_pad_top
            mpb = args.metric_pad_bot
            uml = args.upper_mark_lift
            mgh = args.min_glyph_height
            mbl = args.min_below
            lgap = args.letter_gap
            if args.batch == "vanilla":
                # 2026-10-30 เคยบังคับ minh≈48 → เมนู/Pip-Boy โดนดัน รายการล่างหาย
                # เกมใช้ความสูง glyph จริงเป็นระยะแถว UI — ห้ามพองทุก glyph
                # เผื่อสระไทยด้วย pad เล็กน้อย ไม่ใช้ min_glyph_height ก้อนใหญ่
                # ระยะบรรทัด UI = ความสูง glyph จริง — เพิ่ม pad เพื่อห่างบรรทัด
                # (กรอบ message_menu ขยายตามเนื้อหาใน XML แล้ว จึงพองได้พอประมาณ)
                if mpt is None:
                    mpt = max(2, int(round(size * 0.18)))
                if mpb is None:
                    mpb = max(2, int(round(size * 0.14)))
                if uml is None:
                    uml = 0
                if mgh is None:
                    mgh = 0
                if mbl is None:
                    mbl = max(4, int(round(size * 0.22)))
                if lgap is None:
                    lgap = 0.0
            else:
                mpt = mpt or 0
                mpb = mpb or 0
                uml = uml or 0
                mgh = mgh or 0
                mbl = mbl or 0
                lgap = lgap or 0
            # อย่า lock args.outline ในลูป — คำนวณต่อไฟล์ตามขนาด
            outline = args.outline if args.outline is not None else auto_outline(size)
            sub = argparse.Namespace(
                ttf=args.ttf, name=fname, size=size,
                out=os.path.join(args.out_dir, fname),
                outline=outline, outline_color=args.outline_color,
                outline_inner=args.outline_inner,
                tracking=tracking, letter_gap=lgap,
                line_height=args.line_height or vanilla_lh,
                metric_pad_top=mpt, metric_pad_bot=mpb, upper_mark_lift=uml,
                min_glyph_height=mgh, min_below=mbl,
                match_line_height=bool(args.match_line_height) and not args.no_match_line_height)
            print("--- %s (%dpx)" % (fname, size))
            build(sub)
        return

    if args.metric_pad_top is None:
        args.metric_pad_top = 0
    if args.metric_pad_bot is None:
        args.metric_pad_bot = 0
    if args.upper_mark_lift is None:
        args.upper_mark_lift = 0
    if args.min_glyph_height is None:
        args.min_glyph_height = 0
    if args.min_below is None:
        args.min_below = 0
    if args.letter_gap is None:
        args.letter_gap = 0
    args.match_line_height = bool(args.match_line_height) and not args.no_match_line_height
    build(args)


# ชุดไฟล์ที่ต้องมีในแพ็กเกจ — ชุดหลัก (vanilla slots) และ patch (DarNifiedUINV)
#
# ขนาด px อ้างจาก metrics ของ vanilla (advance ตัวพิมพ์เล็กเฉลี่ย + ความสูงหมึกของ H)
# แล้ว "ลดลง ~15%" เพราะ Sarabun Bold มี x-height สูงและตัวหนากว่า Monofonto
# ทำให้ที่ขนาดเท่ากันดูใหญ่กว่า — ค่าปัจจุบันคือค่าที่ทดสอบในเกมแล้วว่าไม่ล้นกรอบ
#   line_h = ความสูงบรรทัดของ vanilla (header float)
FONTSETS = {
    "vanilla": [
        # (ชื่อไฟล์, ขนาด Sarabun, line height ของ vanilla, tracking = สัดส่วนของขนาด)
        #
        # รอบล่าสุด (2026-10-28): ผู้ใช้ขอให้ลดขนาดในเกมเพิ่ม
        #   gameplay −26%, Pip-Boy −20%, กล่องยืนยันของเมนู −20%
        # สล็อตใน DarNified UI ทับกัน จึงแมปดังนี้:
        #   1 = Pip-Boy list + ข้อความในกล่องยืนยัน  → −20%
        #   4 = HUD meters/ammo + version info       → −26%
        #   6 = quest objective + ปุ่มยืนยัน + Pip-Boy tabs → −26%
        #   7 = start menu + หัวข้อ Pip-Boy + ชื่อสถานที่   → −20%
        # (สล็อต 7 ถูกใช้ร่วมกับ start menu — ผู้ใช้ยืนยันให้ลดไปด้วย)
        # 2026-10-30: ลดขนาดอีก ~14% — กล่องข้อความไทย (หัวข้อ/เนื้อ/ปุ่ม) ล้นกรอบ
        # line_h คงของ vanilla (header); เกมจัดระยะแถวจากความสูง glyph จริง
        # tracking ตาม docs calibrate (≈8–10%)
        ("Glow_Monofonto_Large", 18, 31, 0.089),          # สล็อต 1 เนื้อกล่อง
        ("Monofonto_Large", 17, 31, 0.08),
        ("Glow_Monofonto_Medium", 15, 26, 0.08),
        ("Monofonto_VeryLarge02_Dialogs2", 17, 36, 0.102),  # สล็อต 4
        ("Fixedsys_Comp_uniform_width", 20, 25, None),
        ("Glow_Monofonto_VL_dialogs", 18, 34, 0.08),        # สล็อต 6 ปุ่มกล่อง
        ("Baked-in_Monofonto_Large", 18, 36, 0.089),        # สล็อต 7 หัวข้อกล่อง + start menu
        ("Glow_Futura_Caps_Large", 36, 52, None),
        ("NVFont_Test", 26, 36, None),
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
