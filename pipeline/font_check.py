#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_check.py — ตรวจความถูกต้องของ .fnt/.tex ก่อนติดตั้งเกม

เช็ค:
  - ขนาดไฟล์/จำนวน glyph ครบ 256
  - header name ตรงกับชื่อไฟล์ .tex (เกมโหลด texture ตามชื่อใน header)
  - line height สมเหตุสมผล (8..128)
  - glyph ที่มีหมึก: UV ไม่กลับด้าน (left<right, top<bottom) และสัดส่วนตรงกับ
    px_width × px_height (เทียบกับ texture จริง ±1px)
  - glyph ว่าง: ต้องมี uv เป็น 0 และ advance ≥ 0

Usage:
  python font_check.py ..\\fonts\\out\\vanilla\\Glow_Monofonto_Large.fnt
"""
from __future__ import annotations
import argparse
import os
import struct
import sys

from fnt_lib import load_fnt, load_tex

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def check(fnt_path: str) -> list[str]:
    errs = []
    base = os.path.basename(fnt_path)[:-4]
    tex_path = fnt_path[:-4] + ".tex"
    if not os.path.exists(tex_path):
        return ["ไม่พบไฟล์ .tex คู่กัน: %s" % tex_path]

    with open(fnt_path, "rb") as f:
        line_h = struct.unpack("<f", f.read(4))[0]
    name, glyphs = load_fnt(fnt_path)
    w, h, rgba = load_tex(tex_path)

    if name.lower() != base.lower():
        errs.append("header name %r ไม่ตรงกับชื่อไฟล์ %r (เกมจะหา %s.tex ไม่เจอ)"
                    % (name, base, name))
    if not (8 <= line_h <= 128):
        errs.append("line height ผิดปกติ: %g" % line_h)
    if len(rgba) != w * h * 4:
        errs.append(".tex ข้อมูลไม่ครบ: %d bytes (ต้องการ %d)" % (len(rgba), w * h * 4))

    for cp, g in enumerate(glyphs):
        if g.px_width > 0 or g.px_height > 0:
            if g.uv_right <= g.uv_left or g.uv_bottom <= g.uv_top:
                errs.append("glyph 0x%02X: UV กลับด้าน (L=%.4f R=%.4f T=%.4f B=%.4f)"
                            % (cp, g.uv_left, g.uv_right, g.uv_top, g.uv_bottom))
                continue
            rw = (g.uv_right - g.uv_left) * w
            rh = (g.uv_bottom - g.uv_top) * h
            if abs(rw - g.px_width) > 1.5 or abs(rh - g.px_height) > 1.5:
                errs.append("glyph 0x%02X: สัดส่วนไม่ตรง (uv %.1fx%.1f vs px %.1fx%.1f)"
                            % (cp, rw, rh, g.px_width, g.px_height))
            if g.ascent < -g.px_height - 64 or g.ascent > line_h + 64:
                errs.append("glyph 0x%02X: ascent ผิดปกติ %g (h=%g line_h=%g)"
                            % (cp, g.ascent, g.px_height, line_h))
            if g.advance < 0:
                errs.append("glyph 0x%02X: advance ติดลบ %g" % (cp, g.advance))
        else:
            if g.uv_left or g.uv_right or g.uv_top or g.uv_bottom:
                errs.append("glyph 0x%02X: ว่างแต่มี UV" % cp)
            if g.advance < 0:
                errs.append("glyph 0x%02X: advance ติดลบ %g" % (cp, g.advance))
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fnt", nargs="+")
    args = ap.parse_args()
    bad = 0
    for p in args.fnt:
        errs = check(p)
        if errs:
            bad += 1
            print("FAIL %s" % p)
            for e in errs[:20]:
                print("   - %s" % e)
            if len(errs) > 20:
                print("   ... อีก %d รายการ" % (len(errs) - 20))
        else:
            name, glyphs = load_fnt(p)
            w, h, _ = load_tex(p[:-4] + ".tex")
            print("ok   %s (name=%s atlas=%dx%d line_h=%.0f)"
                  % (os.path.basename(p), name, w, h,
                     struct.unpack("<f", open(p, "rb").read(4))[0]))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
