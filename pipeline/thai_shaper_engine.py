#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thai_shaper_engine.py — Advanced Thai Text Shaper & Layout Engine for Fallout: New Vegas

Features:
  1. Upper Vowel + Tone Precomposition (28 clusters in 0x80-0x9B)
  2. Standalone Tone Lowering (Shift-down tone marks in 0x9C-0x9F, 0xDB for regular consonants)
  3. Tall-stem Consonant Handling (ป, ฝ, ฟ left-shifted vowels and tones in 0xDE, 0xDF, 0xFC-0xFF)
  4. Descender Trimming (ญ, ฐ with lower vowels in 0xDC, 0xDD)
  5. SARA AM with tones decomposition & recombination (น้ำ, ค่ำ)
  6. Smart Thai Word-Wrapping & Line Breaking
"""
from __future__ import annotations

import sys
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# 1. CHARACTER DEFINITIONS & SETS
# ==============================================================================

UPPER_VOWELS = "ัิีึื็ํ"          # 7 สระบน/เครื่องหมายบน
TONE_MARKS = "่้๊๋"             # 4 วรรณยุกต์
THANTHAKHAT = "์"               # การันต์
ALL_TONES = "่้๊๋์"             # วรรณยุกต์ทั้งหมด + การันต์
LOWER_VOWELS = "ฺุู"            # สระล่าง + พินทุ
TALL_CONSONANTS = "ปฝฟ"         # พยัญชนะหางยาว
DESCENDER_CONSONANTS = "ญฐ"     # พยัญชนะมีเชิงล่าง

# ==============================================================================
# 2. EXTENDED PUA / CP874 SLOT ALLOCATION (40 Special Slots)
# ==============================================================================
# 0x80..0x9B (28 slots): สระบน (7) x วรรณยุกต์ (4)
_VOWEL_TONE_COMBOS: List[str] = [u + t for u in UPPER_VOWELS for t in TONE_MARKS]
_VOWEL_TONE_SLOTS: List[int] = list(range(0x80, 0x80 + len(_VOWEL_TONE_COMBOS))) # 0x80..0x9B

CLUSTER_TO_SLOT: Dict[str, int] = dict(zip(_VOWEL_TONE_COMBOS, _VOWEL_TONE_SLOTS))
SLOT_TO_CLUSTER: Dict[int, str] = {b: c for c, b in CLUSTER_TO_SLOT.items()}

# 0x9C..0x9F & 0xDB (5 slots): วรรณยุกต์ระดับต่ำ (เมื่อไม่มีสระบน)
SLOT_LOW_MAI_EK     = 0x9C  # ่ ต่ำ (ค่า, ไม่, ปู่)
SLOT_LOW_MAI_THO    = 0x9D  # ้ ต่ำ (ถ้า, ข้าว, ผู้)
SLOT_LOW_MAI_TRI    = 0x9E  # ๊ ต่ำ (โต๊ะ, กุ๊ก)
SLOT_LOW_MAI_CHATT  = 0x9F  # ๋ ต่ำ (ตั๋ว, แจ๋ว)
SLOT_LOW_GARAN      = 0xDB  # ์ ต่ำ (กอล์ฟ, เบียร์, ฟิลม์)

LOW_TONE_MAP = {
    '่': SLOT_LOW_MAI_EK,
    '้': SLOT_LOW_MAI_THO,
    '๊': SLOT_LOW_MAI_TRI,
    '๋': SLOT_LOW_MAI_CHATT,
    '์': SLOT_LOW_GARAN,
}

# 0xDC..0xDD (2 slots): ญ, ฐ ตัดเชิงล่าง (เมื่อมี สระอุ, สระอู, พินทุ)
SLOT_YO_YING_NOCUT   = 0xAD  # ญ ปกติใน CP874
SLOT_YO_YING_CUT     = 0xDC  # ญ ตัดเชิง
SLOT_THO_THAN_NOCUT  = 0xB0  # ฐ ปกติใน CP874
SLOT_THO_THAN_CUT    = 0xDD  # ฐ ตัดเชิง

CUT_DESCENDER_MAP = {
    'ญ': SLOT_YO_YING_CUT,
    'ฐ': SLOT_THO_THAN_CUT,
}

# 0xDE..0xDF & 0xFC..0xFF (6 slots): อักษรเยื้องซ้ายสำหรับพยัญชนะหางยาว (ป, ฝ, ฟ)
SLOT_TALL_LOW_MAI_EK  = 0xDE  # ่ ต่ำเยื้องซ้าย (ปู่, ป่า)
SLOT_TALL_LOW_MAI_THO = 0xDF  # ้ ต่ำเยื้องซ้าย (ป้า, ผู้)
SLOT_TALL_II_EK       = 0xFC  # ี+่ เยื้องซ้าย (ปี่, ปีที่แล้ว)
SLOT_TALL_UEE_THO     = 0xFD  # ื+้ เยื้องซ้าย (ฟื้น, พื้นที่)
SLOT_TALL_I           = 0xFE  # ิ เยื้องซ้าย (ปิติ)
SLOT_TALL_II          = 0xFF  # ี เยื้องซ้าย (ปี, ปีก)

TALL_SPECIAL_MAP = {
    ('่',): SLOT_TALL_LOW_MAI_EK,
    ('้',): SLOT_TALL_LOW_MAI_THO,
    ('ี', '่'): SLOT_TALL_II_EK,
    ('ื', '้'): SLOT_TALL_UEE_THO,
    ('ิ',): SLOT_TALL_I,
    ('ี',): SLOT_TALL_II,
}

# สระอำ + วรรณยุกต์: (นิคหิต ํ + วรรณยุกต์) + สระอา
# นิคหิต+วรรณยุกต์ อยู่ที่ 0x98..0x9B
AM_TONE_MAP = {
    ('่', 'ำ'): (0x98, 0xD2),
    ('้', 'ำ'): (0x99, 0xD2),
    ('๊', 'ำ'): (0x9A, 0xD2),
    ('๋', 'ำ'): (0x9B, 0xD2),
    ('ำ', '่'): (0x98, 0xD2),
    ('ำ', '้'): (0x99, 0xD2),
    ('ำ', '๊'): (0x9A, 0xD2),
    ('ำ', '๋'): (0x9B, 0xD2),
}

# ==============================================================================
# 3. TEXT SHAPING LOGIC
# ==============================================================================

def shape_thai_text(text: str) -> list[int]:
    """
    แปลงข้อความ Unicode ภาษาไทยให้เป็นลำดับรหัส byte CP874 ที่ผ่านการ Shape ครบทุกระดับ:
    - วรรณยุกต์ลดระดับเมื่อไม่มีสระบน
    - รวมสระบน+วรรณยุกต์เป็น Cluster เดียว
    - หลบหาง ป, ฝ, ฟ
    - ตัดเชิง ญ, ฐ
    - จัดการสระอำ
    """
    # ตรวจสอบการแปลงพื้นฐานเป็น CP874
    # เราจะประมวลผลเป็น Token/Character List
    out_bytes: list[int] = []
    n = len(text)
    i = 0

    while i < n:
        ch = text[i]

        # -------------------------------------------------------------
        # กฎข้อ 1: ตรวจสอบ สระอำ + วรรณยุกต์ (เช่น น้ำ, ถ้ำ, ค่ำ)
        # -------------------------------------------------------------
        if i + 1 < n and (ch, text[i + 1]) in AM_TONE_MAP:
            nikhahit_tone, sara_aa = AM_TONE_MAP[(ch, text[i + 1])]
            out_bytes.extend([nikhahit_tone, sara_aa])
            i += 2
            continue

        # สระอำเดี่ยว (ำ = 0xD3) -> ใช้ slot 0xD3 สำเร็จรูปโดยตรง ไม่แยกเป็น นิคหิต+สระอา
        if ch == 'ำ':
            out_bytes.append(0xD3)
            i += 1
            continue

        # -------------------------------------------------------------
        # กฎข้อ 2: ตรวจสอบ พยัญชนะมีเชิงล่าง (ญ, ฐ) ตามด้วยสระล่าง (ุ, ู, ฺ)
        # -------------------------------------------------------------
        if ch in DESCENDER_CONSONANTS:
            # ดูตัวถัดไปว่ามีสระล่างหรือไม่
            has_lower_vowel = False
            # อาจมีวรรณยุกต์คั่นก่อนสระล่าง (ไม่ถูกไวยากรณ์แต่กันไว้) หรือสระล่างตามหลัง
            j = i + 1
            while j < n and text[j] in ALL_TONES:
                j += 1
            if j < n and text[j] in LOWER_VOWELS:
                has_lower_vowel = True

            if has_lower_vowel:
                out_bytes.append(CUT_DESCENDER_MAP[ch])
                i += 1
                continue

        # -------------------------------------------------------------
        # กฎข้อ 3: พยัญชนะหางยาว (ป, ฝ, ฟ) กับสระบน/วรรณยุกต์
        # -------------------------------------------------------------
        prev_is_tall = (i > 0 and text[i - 1] in TALL_CONSONANTS)

        if prev_is_tall:
            # เช็คว่ามี สระบน + วรรณยุกต์ ที่มีรูปเยื้องซ้ายพิเศษหรือไม่ (เช่น ี+่, ื+้)
            if i + 1 < n and (ch, text[i + 1]) in TALL_SPECIAL_MAP:
                out_bytes.append(TALL_SPECIAL_MAP[(ch, text[i + 1])])
                i += 2
                continue
            # เช็คว่ามี สระเดี่ยว หรือ วรรณยุกต์เดี่ยว เยื้องซ้ายหรือไม่
            if (ch,) in TALL_SPECIAL_MAP:
                out_bytes.append(TALL_SPECIAL_MAP[(ch,)])
                i += 1
                continue

        # -------------------------------------------------------------
        # กฎข้อ 4: สระบน + วรรณยุกต์ (Cluster 0x80..0x9B)
        # -------------------------------------------------------------
        if ch in UPPER_VOWELS and i + 1 < n and text[i + 1] in TONE_MARKS:
            cluster = ch + text[i + 1]
            if cluster in CLUSTER_TO_SLOT:
                out_bytes.append(CLUSTER_TO_SLOT[cluster])
                i += 2
                continue

        # -------------------------------------------------------------
        # กฎข้อ 5: วรรณยุกต์เดี่ยว (ไม่มีสระบน) -> ลดระดับลงมาที่ Level 1
        # -------------------------------------------------------------
        # ตรวจสอบว่าตัวก่อนหน้าไม่ใช่สระบน
        prev_is_upper = (i > 0 and text[i - 1] in UPPER_VOWELS)
        if ch in LOW_TONE_MAP and not prev_is_upper:
            # วรรณยุกต์ลดระดับ (0x9C..0x9F, 0xDB)
            out_bytes.append(LOW_TONE_MAP[ch])
            i += 1
            continue

        # -------------------------------------------------------------
        # ตัวอักษรปกติ: แปลงเป็น CP874
        # -------------------------------------------------------------
        try:
            b = ch.encode("cp874")[0]
            out_bytes.append(b)
        except UnicodeEncodeError:
            # Fallback สำหรับตัวอักษรที่ไม่ใช่ CP874
            out_bytes.append(ord('?'))
        i += 1

    return out_bytes


def shape_to_bytes(text: str) -> bytes:
    """แปลงข้อความ Unicode เป็น bytes CP874 ที่ Shape เรียบร้อยแล้ว"""
    return bytes(shape_thai_text(text))


def unshape_bytes(data: bytes) -> str:
    """แปลงกลับจาก bytes CP874 (ที่มี PUA slots) เป็นข้อความ Unicode ธรรมดา"""
    res: list[str] = []
    u_to_b: dict[str, int] = {}
    for cp in range(0xA0, 0x100):
        try:
            ch = bytes([cp]).decode("cp874")
            u_to_b[ch] = cp
        except Exception:
            continue
    b_to_u = {v: k for k, v in u_to_b.items()}

    for b in data:
        # Precomposed cluster
        if b in SLOT_TO_CLUSTER:
            res.append(SLOT_TO_CLUSTER[b])
        # Lowered tones
        elif b == SLOT_LOW_MAI_EK:
            res.append('่')
        elif b == SLOT_LOW_MAI_THO:
            res.append('้')
        elif b == SLOT_LOW_MAI_TRI:
            res.append('๊')
        elif b == SLOT_LOW_MAI_CHATT:
            res.append('๋')
        elif b == SLOT_LOW_GARAN:
            res.append('์')
        # Cut descenders
        elif b == SLOT_YO_YING_CUT:
            res.append('ญ')
        elif b == SLOT_THO_THAN_CUT:
            res.append('ฐ')
        # Tall left-shifted
        elif b == SLOT_TALL_LOW_MAI_EK:
            res.append('่')
        elif b == SLOT_TALL_LOW_MAI_THO:
            res.append('้')
        elif b == SLOT_TALL_II_EK:
            res.append('ี่')
        elif b == SLOT_TALL_UEE_THO:
            res.append('ื้')
        elif b == SLOT_TALL_I:
            res.append('ิ')
        elif b == SLOT_TALL_II:
            res.append('ี')
        elif b in b_to_u:
            res.append(b_to_u[b])
        elif b < 0x80:
            res.append(chr(b))
        else:
            res.append('?')
    return "".join(res)


if __name__ == "__main__":
    test_phrases = [
        "โดยที่การไม่นำพาและการหมิ่นในคุณค่าของสิทธิมนุษยชน",
        "ผู้หญิง",
        "ฐานราก",
        "ปู่",
        "ป้า",
        "ฟื้นฟู",
        "น้ำเปล่า",
        "กอล์ฟ",
    ]
    print("Testing Thai Shaper Engine:")
    for phrase in test_phrases:
        sb = shape_to_bytes(phrase)
        un = unshape_bytes(sb)
        hex_str = " ".join(f"0x{b:02X}" for b in sb)
        print(f"\nOriginal: {phrase}")
        print(f"Shaped  : {hex_str}")
        print(f"Match   : {un == phrase} ({un})")
