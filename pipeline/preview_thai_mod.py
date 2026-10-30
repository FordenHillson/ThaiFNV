#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preview_thai_mod.py — ดูตัวอย่างข้อความแปลไทยแบบในเกม โดยไม่ต้องเปิด FNV

ใช้ฟอนต์จาก fonts/out + pipeline เดียวกับ ESP:
  wordbreak (sparse) → CP874 + precompose → วาดด้วยสูตร DrawGlyph ของเกม

Usage:
  python preview_thai_mod.py --text "ได้ส่งหนังสือแจ้งการเลิกจ้างเพื่อนร่วมงานแล้ว"
  python preview_thai_mod.py --csv ..\\extracted\\sheets\\from_google\\FNV_Messages.csv --limit 8
  python preview_thai_mod.py --text "..." --font dialog --wrap 360 --out ..\\testing\\preview.png
"""
from __future__ import annotations
import argparse
import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from font_render import parse_color, render
from thai_precompose import encode_thai_cp874
from thai_wordbreak import insert_word_spaces

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
VANILLA = ROOT / "fonts" / "out" / "vanilla"
DARN = ROOT / "fonts" / "out" / "darn"
DEFAULT_OUT = ROOT / "testing" / "preview_thai_mod.png"

# ช่องฟอนต์ที่ใช้บ่อยตอนดูข้อความ UI / ไดอะล็อก
FONT_PRESETS = {
    "hud": VANILLA / "Glow_Monofonto_Large.fnt",          # sFontFile_1
    "dialog": VANILLA / "Monofonto_VeryLarge02_Dialogs2.fnt",  # sFontFile_4
    "pipboy": VANILLA / "Glow_Monofonto_Medium.fnt",      # sFontFile_3
    "books": VANILLA / "Fixedsys_Comp_uniform_width.fnt",  # sFontFile_5
    "darn_body": DARN / "DarN_FranKleinBold_14.fnt",
    "darn_title": DARN / "DarN_Libel_Suit_Otl_24.fnt",
}


def prepare_text(text: str, wordbreak: bool, wb_limit: int) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not wordbreak:
        return text
    # wordbreak ทีละบรรทัด — คง \n ที่ผู้ใช้ใส่
    return "\n".join(
        insert_word_spaces(line, mode="sparse", limit=wb_limit) if line else line
        for line in text.split("\n")
    )


def encode_mod_line(line: str, precompose: bool) -> bytes:
    if precompose:
        return encode_thai_cp874(line)
    return line.encode("cp874", errors="replace")


def load_csv_samples(path: Path, n: int, column: str = "TH") -> list[tuple[str, str]]:
    """คืน [(label, th_text), ...] จากชีตแปล"""
    rows: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            th = (row.get(column) or "").strip()
            if not th or th == "...":
                continue
            eid = (row.get("EditorID") or row.get("FormID") or "").strip()
            en = (row.get("EN") or "").strip()
            label = eid or en[:40] or f"row{len(rows)+1}"
            rows.append((label, th))
            if len(rows) >= n:
                break
    return rows


def stack_panels(panels: list[tuple[str, Image.Image]], bg=(20, 20, 24),
                 label_color=(180, 180, 180)) -> Image.Image:
    """เรียงพาเนลแนวตั้ง พร้อมป้ายชื่อเล็ก ๆ"""
    gap = 10
    label_h = 18
    width = max((im.width for _, im in panels), default=1)
    height = sum(im.height + label_h + gap for _, im in panels) + gap
    out = Image.new("RGBA", (width + 24, height), bg + (255,))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    y = gap
    for label, im in panels:
        draw.text((12, y), label, fill=label_color + (255,), font=font)
        y += label_h
        out.alpha_composite(im, (12, y))
        y += im.height + gap
    return out


def render_sample(fnt: Path, text: str, *, wordbreak: bool, wb_limit: int,
                  precompose: bool, wrap: float, scale: int,
                  color, bg) -> Image.Image:
    prepared = prepare_text(text, wordbreak, wb_limit)
    encoded = [encode_mod_line(line, precompose) for line in prepared.split("\n")]
    return render(
        str(fnt), prepared, scale=scale, color=color, bg=bg,
        precompose=precompose, wrap_width=wrap, encoded_lines=encoded,
    )


def main():
    ap = argparse.ArgumentParser(
        description="Preview ข้อความแปลไทยแบบ pipeline ลงเกม (ไม่ต้องเปิด FNV)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="ข้อความไทย (รองรับ \\n)")
    g.add_argument("--csv", type=Path, help="CSV จาก Sheets (คอลัมน์ TH)")
    ap.add_argument("--limit", type=int, default=6, help="จำนวนแถวจาก CSV")
    ap.add_argument("--font", default="dialog",
                    help="preset: %s หรือ path ไป .fnt" % ", ".join(FONT_PRESETS))
    ap.add_argument("--all-fonts", action="store_true",
                    help="เรนเดอร์ทุก preset ที่มีไฟล์")
    ap.add_argument("--wrap", type=float, default=420,
                    help="ความกว้างกล่องข้อความโดยประมาณ (px ฟอนต์, 0=ไม่ตัด)")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--color", default="E0B93C", help="tint ข้อความ (hex)")
    ap.add_argument("--bg", default="1A140C")
    ap.add_argument("--wb-limit", type=int, default=28, help="sparse wordbreak limit")
    ap.add_argument("--no-wordbreak", action="store_true")
    ap.add_argument("--no-precompose", action="store_true")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if args.font in FONT_PRESETS:
        fonts = [FONT_PRESETS[args.font]]
    else:
        fonts = [Path(args.font)]
    if args.all_fonts:
        fonts = [p for p in FONT_PRESETS.values() if p.is_file()]

    missing = [p for p in fonts if not p.is_file()]
    if missing:
        raise SystemExit("ไม่พบฟอนต์: %s" % ", ".join(str(p) for p in missing))

    if args.text is not None:
        samples = [("text", args.text.replace("\\n", "\n"))]
    else:
        samples = load_csv_samples(args.csv, args.limit)
        if not samples:
            raise SystemExit("CSV ไม่มีแถว TH ที่ใช้ได้")

    color = parse_color(args.color) if args.color else None
    bg = parse_color(args.bg)
    panels: list[tuple[str, Image.Image]] = []

    for label, th in samples:
        for fnt in fonts:
            tag = "%s · %s" % (label, fnt.stem)
            print("render:", tag)
            im = render_sample(
                fnt, th,
                wordbreak=not args.no_wordbreak,
                wb_limit=args.wb_limit,
                precompose=not args.no_precompose,
                wrap=args.wrap,
                scale=args.scale,
                color=color,
                bg=bg,
            )
            panels.append((tag, im))

    out_img = stack_panels(panels, bg=bg)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(args.out)
    print("ok: %s (%dx%d)  panels=%d" % (args.out, out_img.width, out_img.height, len(panels)))


if __name__ == "__main__":
    main()
