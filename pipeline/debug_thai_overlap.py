#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""วินิจฉัยสระ/วรรณยุกต์ทับกัน — วัด metrics จาก .fnt + จำลอง pen แบบเกม"""
from __future__ import annotations
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fnt_lib import load_fnt
from font_builder import COMBINING, is_combining, thai_char_of, THAI_CONSONANTS

# #region agent log
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        ".cursor", "debug-8f0ee2.log")


def dlog(hypothesis_id: str, location: str, message: str, data: dict, run_id: str = "pre"):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    payload = {
        "sessionId": "8f0ee2",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
# #endregion

# ข้อความจาก screenshot ที่เห็นทับชัด
SAMPLES = [
    "หุ่นยนต์",
    "ตรวจสอบ",
    "เปิดใช้งาน",
    "ดูรายละเอียด",
    "Duraframe Eyebot",
]

# กล่องข้อความยืนยัน / บทสนทนา — สล็อตที่น่าจะใช้
FONTS = [
    ("slot1_msg", r"fonts\out\vanilla\Glow_Monofonto_Large.fnt"),
    ("slot6_dialog", r"fonts\out\vanilla\Glow_Monofonto_VL_dialogs.fnt"),
    ("slot4_hud", r"fonts\out\vanilla\Monofonto_VeryLarge02_Dialogs2.fnt"),
]


def ideal_bearing_ink_center(adv_prev: float, iw_prev: float, pad_prev: float,
                             iw_mark: float, pad_mark: float) -> float:
    """bearing ที่จัดกลางหมึกมาร์คให้ตรงกลางหมึกพยัญชนะก่อนหน้า
    หลังวาดพยัญชนะ pen อยู่ที่ปลาย advance; ขอบซ้ายมาร์ค = pen + bearing
    หมึกมาร์คเริ่มที่ bearing + pad_mark
    """
    # ศูนย์พยัญชนะเทียบ pen ปัจจุบัน: -adv_prev + pad_prev + iw_prev/2
    # ศูนย์มาร์ค: bearing + pad_mark + iw_mark/2
    return -adv_prev + pad_prev + iw_prev / 2.0 - pad_mark - iw_mark / 2.0


def ideal_bearing_simple(adv_prev: float, iw_mark: float) -> float:
    """สูตรใน docs: -(adv + iw_mark)/2  ≈ จัดกลางในกล่อง advance"""
    return -(adv_prev + iw_mark) / 2.0


def analyze_font(label: str, path: str, root: str, run_id: str):
    full = os.path.join(root, path)
    if not os.path.isfile(full):
        dlog("C", "debug_thai_overlap.py:missing", "font missing",
             {"label": label, "path": full}, run_id)
        return
    name, glyphs = load_fnt(full)

    # #region agent log — H-C: combining advance ต้องเป็น 0
    comb_rows = []
    for cp in range(0xA0, 0x100):
        ch = thai_char_of(cp)
        if ch is None or not is_combining(ch):
            continue
        g = glyphs[cp]
        comb_rows.append({
            "cp": "0x%02X" % cp,
            "ch": ch,
            "w": round(g.px_width, 2),
            "bearing": round(g.bearing_x, 2),
            "advance": round(g.advance, 2),
            "adv_extra": round(g.advance_extra, 2),
            "ascent": round(g.ascent, 2),
        })
    nonzero_adv = [r for r in comb_rows if abs(r["advance"]) > 0.01]
    dlog("C", "debug_thai_overlap.py:combining_table",
         "combining glyph metrics",
         {"label": label, "font": name, "count": len(comb_rows),
          "nonzero_advance": nonzero_adv[:8],
          "sample": comb_rows[:6]},
         run_id)
    # #endregion

    # ความกว้างพยัญชนะเฉลี่ยจากฟอนต์ที่ build แล้ว
    cons = []
    for cp in THAI_CONSONANTS:
        g = glyphs[cp]
        if g.px_width > 0:
            cons.append({
                "cp": cp, "w": g.px_width, "adv": g.advance, "bearing": g.bearing_x,
            })
    avg_adv = sum(c["adv"] for c in cons) / len(cons) if cons else 0
    avg_w = sum(c["w"] for c in cons) / len(cons) if cons else 0
    # pad โดยประมาณ: non-combining มี bearing=0 และ w > ink — ประมาณ (w ใหญ่ - adv?) ไม่แม่น
    # ใช้ outline pad จากส่วนต่าง w กับ advance ของพยัญชนะไม่ได้ตรง ๆ
    dlog("A", "debug_thai_overlap.py:cons_stats",
         "consonant avg metrics",
         {"label": label, "avg_adv": round(avg_adv, 2), "avg_w": round(avg_w, 2),
          "bearing_all_zero": all(abs(c["bearing"]) < 0.01 for c in cons),
          "n": len(cons)},
         run_id)

    for text in SAMPLES:
        try:
            raw = text.encode("cp874")
        except UnicodeEncodeError:
            continue
        pen = 0.0
        placed = []
        overlaps = []
        for i, b in enumerate(raw):
            g = glyphs[b]
            ch = bytes([b]).decode("cp874", "replace")
            x0 = pen + g.bearing_x
            x1 = x0 + g.px_width
            entry = {
                "i": i, "ch": ch, "cp": "0x%02X" % b,
                "combining": is_combining(ch),
                "pen": round(pen, 2),
                "bearing": round(g.bearing_x, 2),
                "w": round(g.px_width, 2),
                "adv": round(g.advance, 2),
                "x0": round(x0, 2),
                "x1": round(x1, 2),
            }
            if is_combining(ch):
                # เทียบสูตรในโค้ดปัจจุบัน vs สูตร docs vs สูตรจัดกลางหมึก
                # สมมติ pad ≈ (avg_w - avg_adv) ไม่ได้ — ใช้ pad ประมาณจาก auto_outline
                # จาก builder: pad = outline+1, outline=1 if size<20 else 2 → pad 2 หรือ 3
                # วัดจาก bearing สูตรปัจจุบัน: bearing = (ref - iw)/2 - round(ref+track)
                # เราเทียบกับ ideal จาก avg_adv
                ideal_docs = ideal_bearing_simple(avg_adv, max(1.0, g.px_width - 4))
                # pad≈2 (outline 1+1) หรือ 3
                for pad_guess in (2.0, 3.0):
                    iw_guess = max(1.0, g.px_width - 2 * pad_guess)
                    ideal_ink = ideal_bearing_ink_center(
                        avg_adv, avg_w - 2 * pad_guess, pad_guess,
                        iw_guess, pad_guess)
                    entry["ideal_ink_pad%.0f" % pad_guess] = round(ideal_ink, 2)
                entry["ideal_docs"] = round(ideal_docs, 2)
                entry["delta_vs_docs"] = round(g.bearing_x - ideal_docs, 2)
                entry["delta_vs_ink_pad2"] = round(
                    g.bearing_x - entry.get("ideal_ink_pad2", 0), 2)
            placed.append(entry)
            # overlap กับ glyph ก่อนหน้าที่ไม่ใช่ combining ของตัวเองซ้อนทับหนัก
            if len(placed) >= 2 and g.px_width > 0:
                prev = placed[-2]
                overlap_px = prev["x1"] - x0
                if overlap_px > 2 and not (prev["combining"] and is_combining(ch)):
                    # มาร์คทับพยัญชนะเป็นเรื่องปกติถ้าจัดกลาง — แต่ถ้าทับตัวถัดไปผิด
                    pass
                if is_combining(ch) and len(placed) >= 3:
                    # ตรวจว่ามาร์คยื่นเข้าไปในพยัญชนะตัวถัดไปมากแค่ไหน
                    # หลังมาร์คยังไม่ advance — ตัวถัดไปจะมาทีหลัง
                    pass
            pen += g.advance

        # ผ่านรอบสอง: หาคู่พยัญชนะ+มาร์ค แล้วดูว่ามาร์คทับพยัญชนะตัวถัดไปไหม
        for i, e in enumerate(placed):
            if not e["combining"]:
                continue
            # หาพยัญชนะถัดไปหลังมาร์ค (อาจมีมาร์คซ้อน)
            nxt = None
            for j in range(i + 1, len(placed)):
                if not placed[j]["combining"]:
                    nxt = placed[j]
                    break
            if nxt and e["x1"] > nxt["x0"] + 1:
                overlaps.append({
                    "mark": e["ch"], "mark_x1": e["x1"],
                    "next": nxt["ch"], "next_x0": nxt["x0"],
                    "overlap_into_next": round(e["x1"] - nxt["x0"], 2),
                })
            # มาร์คยื่นซ้ายเกินขอบพยัญชนะก่อนหน้าหรือไม่
            prev_base = None
            for j in range(i - 1, -1, -1):
                if not placed[j]["combining"]:
                    prev_base = placed[j]
                    break
            if prev_base:
                overhang_left = prev_base["x0"] - e["x0"]
                overhang_right = e["x1"] - prev_base["x1"]
                e["overhang_left"] = round(overhang_left, 2)
                e["overhang_right"] = round(overhang_right, 2)

        # #region agent log
        dlog("A", "debug_thai_overlap.py:layout",
             "pen layout for sample",
             {"label": label, "text": text, "glyphs": placed,
              "overlaps_into_next": overlaps},
             run_id)
        dlog("B", "debug_thai_overlap.py:bearing_delta",
             "combining bearing vs ideal",
             {"label": label, "text": text,
              "marks": [{
                  "ch": e["ch"],
                  "bearing": e["bearing"],
                  "ideal_docs": e.get("ideal_docs"),
                  "ideal_ink_pad2": e.get("ideal_ink_pad2"),
                  "ideal_ink_pad3": e.get("ideal_ink_pad3"),
                  "delta_docs": e.get("delta_vs_docs"),
                  "delta_ink2": e.get("delta_vs_ink_pad2"),
                  "overhang_L": e.get("overhang_left"),
                  "overhang_R": e.get("overhang_right"),
                  "w": e["w"],
              } for e in placed if e["combining"]]},
             run_id)
        # #endregion

        # H-E: ความกว้างมาร์คเทียบพยัญชนะ — outline ทำให้กว้างเกิน?
        marks_w = [e["w"] for e in placed if e["combining"]]
        bases_w = [e["w"] for e in placed if not e["combining"] and e["w"] > 0]
        if marks_w and bases_w:
            dlog("E", "debug_thai_overlap.py:mark_width",
                 "mark vs base widths",
                 {"label": label, "text": text,
                  "mark_ws": marks_w, "base_ws": bases_w,
                  "max_mark": max(marks_w), "avg_base": round(sum(bases_w)/len(bases_w), 2)},
                 run_id)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    run_id = "pre"
    if len(sys.argv) > 1:
        run_id = sys.argv[1]
    dlog("A", "debug_thai_overlap.py:start", "debug run start",
         {"run_id": run_id, "samples": SAMPLES}, run_id)
    for label, path in FONTS:
        analyze_font(label, path, root, run_id)
    print("ok: wrote logs to", LOG_PATH)


if __name__ == "__main__":
    main()
