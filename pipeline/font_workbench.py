#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_workbench.py — GUI เฟส 1: พรีวิวข้อความแปลไทย + แก้ glyph metrics/UV

Dear PyGui · สูตรวาดตาม FalloutNV DrawGlyph · เซฟชุดใหม่ที่ fonts/out/preview_edit/

Usage:
  python font_workbench.py
  python font_workbench.py --fnt ..\\fonts\\out\\vanilla\\Monofonto_VeryLarge02_Dialogs2.fnt
"""
from __future__ import annotations

import argparse
import copy
import csv
import struct
import sys
import time
from pathlib import Path

import dearpygui.dearpygui as dpg
from PIL import Image

from fnt_lib import NUM_GLYPHS, Glyph, load_fnt, load_tex, save_fnt, save_tex
from font_render import render
from thai_precompose import encode_thai_cp874
from thai_wordbreak import insert_word_spaces

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
VANILLA = ROOT / "fonts" / "out" / "vanilla"
DARN = ROOT / "fonts" / "out" / "darn"
EDIT_ROOT = ROOT / "fonts" / "out" / "preview_edit"
UI_FONT = ROOT / "fonts" / "src" / "Sarabun-Regular.ttf"

FONT_PRESETS = {
    "hud": VANILLA / "Glow_Monofonto_Large.fnt",
    "dialog": VANILLA / "Monofonto_VeryLarge02_Dialogs2.fnt",
    "pipboy": VANILLA / "Glow_Monofonto_Medium.fnt",
    "books": VANILLA / "Fixedsys_Comp_uniform_width.fnt",
    "darn_body": DARN / "DarN_FranKleinBold_14.fnt",
    "darn_title": DARN / "DarN_Libel_Suit_Otl_24.fnt",
}

ATLAS_VIEW = 384
PREVIEW_W = 640
PREVIEW_H = 280


def pil_to_float_rgba(img: Image.Image) -> list[float]:
    img = img.convert("RGBA")
    px = img.tobytes()
    return [c / 255.0 for c in px]


def parse_hex_color(text: str, fallback=(224, 185, 60)):
    t = (text or "").strip().lstrip("#")
    if len(t) != 6:
        return fallback
    try:
        return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def glyph_label(i: int) -> str:
    if 32 <= i < 127:
        return "%02X '%s'" % (i, chr(i))
    return "%02X" % i


class Workbench:
    def __init__(self, initial_fnt: Path | None = None):
        self.source_path: Path | None = None
        self.font_name = ""
        self.line_height = 40.0
        self.tex_w = 1
        self.tex_h = 1
        self.atlas_img: Image.Image | None = None
        self.source_glyphs: list[Glyph] = []
        self.work_glyphs: list[Glyph] = []
        self.glyph_baseline: Glyph | None = None
        self.selected = 0x41
        self.dirty = False
        self._suppress = False
        self._preview_due = 0.0
        self._atlas_tex_tag = "atlas_raw"
        self._preview_a_tag = "preview_a_raw"
        self._preview_b_tag = "preview_b_raw"
        self.initial_fnt = initial_fnt or FONT_PRESETS["dialog"]

    # ------------------------------------------------------------------ load
    def load_font(self, path: Path, *, as_source: bool = True):
        path = Path(path)
        name, glyphs = load_fnt(str(path))
        with open(path, "rb") as f:
            line_height = struct.unpack("<f", f.read(4))[0]
        tw, th, rgba = load_tex(str(path.with_suffix(".tex")))
        self.font_name = name
        self.line_height = line_height
        self.tex_w, self.tex_h = tw, th
        self.atlas_img = Image.frombytes("RGBA", (tw, th), rgba)
        if as_source:
            self.source_path = path
            self.source_glyphs = copy.deepcopy(glyphs)
            self.work_glyphs = copy.deepcopy(glyphs)
            self.dirty = False
        else:
            # โหลดเป็น working อย่างเดียว (ไม่ใช้ในเฟส 1)
            self.work_glyphs = copy.deepcopy(glyphs)
        self._capture_baseline()
        self._push_all_ui()
        self.queue_preview()

    def _capture_baseline(self):
        self.glyph_baseline = copy.deepcopy(self.work_glyphs[self.selected])

    # ------------------------------------------------------------------ UV helpers
    def glyph_px_box(self, g: Glyph) -> tuple[float, float, float, float]:
        return (
            g.uv_left * self.tex_w,
            g.uv_top * self.tex_h,
            g.uv_right * self.tex_w,
            g.uv_bottom * self.tex_h,
        )

    def apply_px_box(self, g: Glyph, l: float, t: float, r: float, b: float):
        l = max(0.0, min(l, self.tex_w))
        t = max(0.0, min(t, self.tex_h))
        r = max(l + 1.0, min(r, self.tex_w))
        b = max(t + 1.0, min(b, self.tex_h))
        g.set_uv(l / self.tex_w, t / self.tex_h, r / self.tex_w, b / self.tex_h)
        g.px_width = r - l
        g.px_height = b - t

    # ------------------------------------------------------------------ UI sync
    def _push_all_ui(self):
        self._suppress = True
        try:
            if self.source_path:
                dpg.set_value("lbl_source", str(self.source_path))
            dpg.set_value("lbl_font_name", self.font_name)
            dpg.set_value("inp_line_height", self.line_height)
            dpg.set_value("inp_glyph_idx", self.selected)
            dpg.set_value("lbl_glyph", glyph_label(self.selected))
            self._push_glyph_sliders()
            self._update_atlas_texture()
            self._redraw_uv_overlay()
            dpg.set_value("lbl_dirty", "มีแก้ยังไม่เซฟ" if self.dirty else "สะอาด")
            dpg.set_value(
                "lbl_warn",
                "คำเตือน: rebuild จาก TTF (font_builder) อาจทับไฟล์ใน fonts/out ต้นทาง — "
                "ชุดที่เซฟไว้ที่ preview_edit จะไม่ถูกลบอัตโนมัติ",
            )
            for tag in ("sl_left", "sl_top", "sl_right", "sl_bottom"):
                if dpg.does_item_exist(tag):
                    dpg.configure_item(
                        tag,
                        max_value=float(max(self.tex_w, self.tex_h, 64)),
                    )
        finally:
            self._suppress = False

    def _push_glyph_sliders(self):
        g = self.work_glyphs[self.selected]
        l, t, r, b = self.glyph_px_box(g)
        self._suppress = True
        try:
            dpg.set_value("sl_left", l)
            dpg.set_value("sl_top", t)
            dpg.set_value("sl_right", r)
            dpg.set_value("sl_bottom", b)
            dpg.set_value("sl_bearing", g.bearing_x)
            dpg.set_value("sl_adv_extra", g.advance_extra)
            dpg.set_value("sl_ascent", g.ascent)
            dpg.set_value("lbl_wh", "width=%.1f  height=%.1f  advance=%.1f" % (
                g.px_width, g.px_height, g.advance))
        finally:
            self._suppress = False

    def _update_atlas_texture(self):
        if self.atlas_img is None:
            return
        from PIL import ImageDraw
        # atlas มักโปร่งใส → วางบนพื้นเทาเข้มก่อน ไม่งั้นใน DPG ดูดำว่าง
        scaled = self.atlas_img.resize((ATLAS_VIEW, ATLAS_VIEW), Image.NEAREST).convert("RGBA")
        view = Image.new("RGBA", (ATLAS_VIEW, ATLAS_VIEW), (36, 36, 40, 255))
        view.alpha_composite(scaled)
        if self.work_glyphs:
            g = self.work_glyphs[self.selected]
            sx = ATLAS_VIEW / max(self.tex_w, 1)
            sy = ATLAS_VIEW / max(self.tex_h, 1)
            x1 = int(g.uv_left * self.tex_w * sx)
            y1 = int(g.uv_top * self.tex_h * sy)
            x2 = int(g.uv_right * self.tex_w * sx)
            y2 = int(g.uv_bottom * self.tex_h * sy)
            draw = ImageDraw.Draw(view)
            draw.rectangle((x1, y1, x2, y2), outline=(255, 220, 60, 255), width=2)
        data = pil_to_float_rgba(view)
        if dpg.does_item_exist(self._atlas_tex_tag):
            dpg.set_value(self._atlas_tex_tag, data)

    def _redraw_uv_overlay(self):
        self._update_atlas_texture()

    # ------------------------------------------------------------------ edits
    def select_glyph(self, idx: int):
        idx = max(0, min(255, int(idx)))
        if idx == self.selected and self.glyph_baseline is not None:
            self._push_glyph_sliders()
            self._redraw_uv_overlay()
            return
        self.selected = idx
        self._capture_baseline()
        self._suppress = True
        try:
            dpg.set_value("inp_glyph_idx", idx)
            dpg.set_value("lbl_glyph", glyph_label(idx))
        finally:
            self._suppress = False
        self._push_glyph_sliders()
        self._redraw_uv_overlay()
        self.queue_preview()

    def on_metrics_change(self):
        if self._suppress or not self.work_glyphs:
            return
        g = self.work_glyphs[self.selected]
        l = float(dpg.get_value("sl_left"))
        t = float(dpg.get_value("sl_top"))
        r = float(dpg.get_value("sl_right"))
        b = float(dpg.get_value("sl_bottom"))
        self.apply_px_box(g, l, t, r, b)
        g.bearing_x = float(dpg.get_value("sl_bearing"))
        g.advance_extra = float(dpg.get_value("sl_adv_extra"))
        g.ascent = float(dpg.get_value("sl_ascent"))
        self.line_height = float(dpg.get_value("inp_line_height"))
        self.dirty = True
        dpg.set_value("lbl_dirty", "มีแก้ยังไม่เซฟ")
        dpg.set_value("lbl_wh", "width=%.1f  height=%.1f  advance=%.1f" % (
            g.px_width, g.px_height, g.advance))
        # sync sliders if clamp changed box
        self._suppress = True
        try:
            l2, t2, r2, b2 = self.glyph_px_box(g)
            dpg.set_value("sl_left", l2)
            dpg.set_value("sl_top", t2)
            dpg.set_value("sl_right", r2)
            dpg.set_value("sl_bottom", b2)
        finally:
            self._suppress = False
        self._redraw_uv_overlay()
        self.queue_preview()

    def reset_selected_glyph(self):
        if self.glyph_baseline is None:
            return
        self.work_glyphs[self.selected] = copy.deepcopy(self.glyph_baseline)
        self.dirty = True
        self._push_glyph_sliders()
        self._redraw_uv_overlay()
        self.queue_preview()

    def revert_selected_to_source(self):
        self.work_glyphs[self.selected] = copy.deepcopy(self.source_glyphs[self.selected])
        self._capture_baseline()
        self.dirty = True
        self._push_glyph_sliders()
        self._redraw_uv_overlay()
        self.queue_preview()

    # ------------------------------------------------------------------ preview text
    def _preview_text(self) -> str:
        return (dpg.get_value("inp_text") or "").replace("\\n", "\n")

    def _prepare_encoded(self, text: str) -> list[bytes]:
        wb = bool(dpg.get_value("chk_wordbreak"))
        pre = bool(dpg.get_value("chk_precompose"))
        limit = int(dpg.get_value("sl_wb_limit"))
        lines_out: list[bytes] = []
        for line in text.split("\n"):
            if wb and line:
                line = insert_word_spaces(line, mode="sparse", limit=limit)
            if pre:
                lines_out.append(encode_thai_cp874(line))
            else:
                lines_out.append(line.encode("cp874", errors="replace"))
        return lines_out

    def _temp_fnt_bundle(self, glyphs: list[Glyph], folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        fnt = folder / "_workbench_preview.fnt"
        tex = folder / "_workbench_preview.tex"
        save_fnt(str(fnt), self.font_name or "preview", glyphs, line_height=self.line_height)
        assert self.atlas_img is not None
        save_tex(str(tex), self.tex_w, self.tex_h, self.atlas_img.tobytes())
        # texture name inside fnt must match stem for load_tex companion — font_render uses path[:-4]+.tex
        return fnt

    def _glyphs_for_compare_side(self, side: str) -> list[Glyph]:
        """side: work | baseline | source"""
        mode = dpg.get_value("cmp_mode")
        if side == "work":
            return self.work_glyphs
        if mode == "ไฟล์ต้นทาง vs ชุดแก้":
            return self.source_glyphs if side == "before" else self.work_glyphs
        # ค่าก่อนแก้ glyph vs ตอนนี้
        if side == "before":
            g = copy.deepcopy(self.work_glyphs)
            if self.glyph_baseline is not None:
                g[self.selected] = copy.deepcopy(self.glyph_baseline)
            return g
        return self.work_glyphs

    def queue_preview(self):
        self._preview_due = time.time() + 0.12

    def tick_preview(self):
        if self._preview_due and time.time() >= self._preview_due:
            self._preview_due = 0.0
            self.refresh_preview()

    def refresh_preview(self):
        if not self.work_glyphs or self.atlas_img is None:
            return
        text = self._preview_text()
        if not text.strip():
            text = "Aa กข คำไทย ที่ เปลี่ยน"
        wrap = float(dpg.get_value("sl_wrap"))
        scale = int(dpg.get_value("sl_scale"))
        color = parse_hex_color(dpg.get_value("inp_fg"), (224, 185, 60))
        bg = parse_hex_color(dpg.get_value("inp_bg"), (26, 20, 12))
        encoded = self._prepare_encoded(text)

        tmp = ROOT / "testing" / "_workbench_tmp"
        sides = [
            ("before", self._preview_a_tag, "img_preview_a"),
            ("work", self._preview_b_tag, "img_preview_b"),
        ]
        for side, tex_tag, img_tag in sides:
            glyphs = self._glyphs_for_compare_side(side)
            fnt = self._temp_fnt_bundle(glyphs, tmp / side)
            try:
                im = render(
                    str(fnt), text, scale=scale, color=color, bg=bg,
                    precompose=True, wrap_width=wrap, encoded_lines=encoded,
                )
            except Exception as e:
                dpg.set_value("lbl_status", "preview error: %s" % e)
                return
            canvas = Image.new("RGBA", (PREVIEW_W, PREVIEW_H), bg + (255,))
            im = im.convert("RGBA")
            # fit
            if im.width > PREVIEW_W or im.height > PREVIEW_H:
                im.thumbnail((PREVIEW_W, PREVIEW_H), Image.NEAREST)
            canvas.paste(im, (0, 0), im)
            data = pil_to_float_rgba(canvas)
            if dpg.does_item_exist(tex_tag):
                dpg.set_value(tex_tag, data)
        dpg.set_value("lbl_status", "พรีวิวอัปเดต · glyph %s" % glyph_label(self.selected))

    # ------------------------------------------------------------------ CSV
    def load_csv(self):
        path = Path(dpg.get_value("inp_csv") or "")
        if not path.is_file():
            dpg.set_value("lbl_status", "ไม่พบ CSV: %s" % path)
            return
        col = dpg.get_value("inp_csv_col") or "TH"
        n = max(1, int(dpg.get_value("sl_csv_rows")))
        lines: list[str] = []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                th = (row.get(col) or "").strip()
                if not th or th == "...":
                    continue
                lines.append(th)
                if len(lines) >= n:
                    break
        if not lines:
            dpg.set_value("lbl_status", "CSV ไม่มีข้อความในคอลัมน์ %s" % col)
            return
        dpg.set_value("inp_text", "\n\n".join(lines))
        dpg.set_value("lbl_status", "โหลด CSV %d แถว" % len(lines))
        self.queue_preview()

    # ------------------------------------------------------------------ save
    def save_edit_set(self):
        if not self.source_path or self.atlas_img is None:
            return
        stem = self.source_path.stem
        out_dir = EDIT_ROOT / stem
        out_dir.mkdir(parents=True, exist_ok=True)
        fnt_path = out_dir / (stem + ".fnt")
        tex_path = out_dir / (stem + ".tex")
        # ชื่อใน header ควรชี้ชื่อ texture เดียวกับไฟล์เกม
        save_fnt(str(fnt_path), self.font_name, self.work_glyphs, line_height=self.line_height)
        save_tex(str(tex_path), self.tex_w, self.tex_h, self.atlas_img.tobytes())
        self.dirty = False
        if dpg.does_item_exist("lbl_dirty"):
            dpg.set_value("lbl_dirty", "สะอาด")
        if dpg.does_item_exist("lbl_status"):
            dpg.set_value("lbl_status", "เซฟแล้ว: %s" % out_dir)
        if dpg.does_item_exist("lbl_warn"):
            dpg.set_value(
                "lbl_warn",
                "เซฟที่ %s — rebuild จาก TTF จะไม่ทับโฟลเดอร์นี้โดยอัตโนมัติ "
                "แต่ถ้า Deploy ทับเกมด้วยไฟล์จาก fonts/out ต้นทาง งานมือจะไม่โผล่ในเกม"
                % out_dir,
            )

    # ------------------------------------------------------------------ build UI
    def build(self):
        dpg.create_context()

        # Dear PyGui ฟอนต์เริ่มต้นไม่มีไทย → ต้อง bind TTF เอง ไม่งั้นได้ "???"
        if not UI_FONT.is_file():
            raise SystemExit("ไม่พบฟอนต์ UI: %s" % UI_FONT)
        with dpg.font_registry():
            # DPG 2.3+ โหลดครบทุก glyph ในไฟล์อัตโนมัติ (รวมไทยใน Sarabun)
            dpg.add_font(str(UI_FONT), 18, tag="ui_font")
        dpg.bind_font("ui_font")

        # placeholder textures
        blank_atlas = [0.1] * (ATLAS_VIEW * ATLAS_VIEW * 4)
        blank_prev = [0.08] * (PREVIEW_W * PREVIEW_H * 4)
        with dpg.texture_registry(tag="tex_reg"):
            dpg.add_raw_texture(
                ATLAS_VIEW, ATLAS_VIEW, blank_atlas,
                format=dpg.mvFormat_Float_rgba, tag=self._atlas_tex_tag)
            dpg.add_raw_texture(
                PREVIEW_W, PREVIEW_H, blank_prev,
                format=dpg.mvFormat_Float_rgba, tag=self._preview_a_tag)
            dpg.add_raw_texture(
                PREVIEW_W, PREVIEW_H, blank_prev.copy(),
                format=dpg.mvFormat_Float_rgba, tag=self._preview_b_tag)

        with dpg.window(tag="main", label="ThaiFNV Font Workbench (phase 1)"):
            with dpg.group(horizontal=True):
                # ---- left: file + glyph pick + metrics
                with dpg.child_window(width=360, height=860, border=True):
                    dpg.add_text("ฟอนต์ที่แก้")
                    dpg.add_text("", tag="lbl_source", wrap=340)
                    dpg.add_text("", tag="lbl_font_name")
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="โหลด…", callback=lambda: self._open_file_dialog())
                        dpg.add_combo(
                            list(FONT_PRESETS.keys()), default_value="dialog",
                            tag="cmb_load_preset", width=120,
                            callback=lambda: self.load_font(
                                FONT_PRESETS[dpg.get_value("cmb_load_preset")]))
                        dpg.add_button(
                            label="โหลด preset",
                            callback=lambda: self.load_font(
                                FONT_PRESETS[dpg.get_value("cmb_load_preset")]))
                    dpg.add_input_float(
                        label="line_height", tag="inp_line_height",
                        default_value=40, width=120,
                        callback=lambda: self.on_metrics_change())
                    dpg.add_separator()
                    dpg.add_text("Glyph")
                    with dpg.group(horizontal=True):
                        dpg.add_input_int(
                            tag="inp_glyph_idx", default_value=0x41, width=80,
                            min_value=0, max_value=255,
                            callback=lambda: self.select_glyph(dpg.get_value("inp_glyph_idx")))
                        dpg.add_button(label="−", width=30,
                                       callback=lambda: self.select_glyph(self.selected - 1))
                        dpg.add_button(label="+", width=30,
                                       callback=lambda: self.select_glyph(self.selected + 1))
                        dpg.add_text("", tag="lbl_glyph")
                    dpg.add_text("", tag="lbl_wh")
                    dpg.add_separator()
                    dpg.add_text("กล่อง UV (px) — ผูก width/height")
                    for tag, lab, mx in (
                        ("sl_left", "left", 1024),
                        ("sl_top", "top", 1024),
                        ("sl_right", "right", 1024),
                        ("sl_bottom", "bottom", 1024),
                    ):
                        dpg.add_slider_float(
                            label=lab, tag=tag, default_value=0, min_value=0,
                            max_value=float(mx), width=220,
                            callback=lambda: self.on_metrics_change())
                    dpg.add_separator()
                    dpg.add_text("Pen metrics (สูตรเกม)")
                    dpg.add_slider_float(
                        label="bearing_x", tag="sl_bearing", default_value=0,
                        min_value=-64, max_value=64, width=220,
                        callback=lambda: self.on_metrics_change())
                    dpg.add_slider_float(
                        label="advance_extra", tag="sl_adv_extra", default_value=0,
                        min_value=-64, max_value=64, width=220,
                        callback=lambda: self.on_metrics_change())
                    dpg.add_slider_float(
                        label="ascent", tag="sl_ascent", default_value=0,
                        min_value=-64, max_value=128, width=220,
                        callback=lambda: self.on_metrics_change())
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="รีเซ็ต glyph (ค่าตอนเลือก)",
                                       callback=lambda: self.reset_selected_glyph())
                        dpg.add_button(label="คืนค่าจากไฟล์ต้นทาง",
                                       callback=lambda: self.revert_selected_to_source())
                    dpg.add_separator()
                    dpg.add_button(label="เซฟชุดใหม่ → preview_edit/",
                                   callback=lambda: self.save_edit_set())
                    dpg.add_text("", tag="lbl_dirty")
                    dpg.add_text("", tag="lbl_warn", wrap=340, color=(220, 180, 100))

                    dpg.add_separator()
                    dpg.add_text("เลือกเร็ว")
                    with dpg.child_window(height=220, border=True):
                        def _row(indices):
                            with dpg.group(horizontal=True):
                                for i in indices:
                                    lab = chr(i) if 32 <= i < 127 else "%02X" % i
                                    dpg.add_button(
                                        label=lab, width=28, height=22,
                                        user_data=i,
                                        callback=lambda s, a, u: self.select_glyph(u))
                        for row in range(6):
                            start = 0x20 + row * 16
                            _row(range(start, min(start + 16, 0x80)))
                        dpg.add_text("precompose 80-9B / ไทย A1-FF")
                        _row(range(0x80, 0x90))
                        _row(range(0x90, 0xA0))
                        _row(range(0xA1, 0xB1))
                        _row(range(0xB1, 0xC1))
                        _row(range(0xC1, 0xD1))
                        _row(range(0xD1, 0xE1))
                        _row(range(0xE1, 0xF1))
                        _row(range(0xF1, 0x100))

                # ---- center: atlas
                with dpg.child_window(width=ATLAS_VIEW + 24, height=860, border=True):
                    dpg.add_text("Atlas + กรอบ UV")
                    dpg.add_image(self._atlas_tex_tag, tag="img_atlas")
                    dpg.add_text("เฟส 1: ปรับกล่องด้วยสไลเดอร์ (ลากขอบ = เฟสถัดไป)")

                # ---- right: preview
                with dpg.child_window(width=PREVIEW_W + 40, height=860, border=True):
                    dpg.add_text("พรีวิวข้อความ (สูตรเกม)")
                    dpg.add_input_text(
                        tag="inp_text", multiline=True, height=90, width=PREVIEW_W,
                        default_value="ได้ส่งหนังสือแจ้งการเลิกจ้างเพื่อนร่วมงานแล้ว\nที่ เปลี่ยน ถูกต้อง",
                        callback=lambda: self.queue_preview())
                    with dpg.group(horizontal=True):
                        dpg.add_checkbox(label="wordbreak", tag="chk_wordbreak",
                                         default_value=True, callback=lambda: self.queue_preview())
                        dpg.add_checkbox(label="precompose", tag="chk_precompose",
                                         default_value=True, callback=lambda: self.queue_preview())
                        dpg.add_slider_int(
                            label="wb-limit", tag="sl_wb_limit", default_value=28,
                            min_value=8, max_value=64, width=140,
                            callback=lambda: self.queue_preview())
                    with dpg.group(horizontal=True):
                        dpg.add_slider_float(
                            label="wrap", tag="sl_wrap", default_value=420,
                            min_value=0, max_value=800, width=180,
                            callback=lambda: self.queue_preview())
                        dpg.add_slider_int(
                            label="scale", tag="sl_scale", default_value=2,
                            min_value=1, max_value=4, width=120,
                            callback=lambda: self.queue_preview())
                    with dpg.group(horizontal=True):
                        dpg.add_input_text(label="fg", tag="inp_fg", default_value="E0B93C",
                                           width=80, callback=lambda: self.queue_preview())
                        dpg.add_input_text(label="bg", tag="inp_bg", default_value="1A140C",
                                           width=80, callback=lambda: self.queue_preview())
                    dpg.add_separator()
                    dpg.add_text("CSV")
                    dpg.add_input_text(
                        tag="inp_csv", width=PREVIEW_W,
                        default_value=str(
                            ROOT / "extracted" / "sheets" / "from_google" / "FNV_Messages.csv"))
                    with dpg.group(horizontal=True):
                        dpg.add_input_text(label="คอลัมน์", tag="inp_csv_col",
                                           default_value="TH", width=60)
                        dpg.add_slider_int(label="แถว", tag="sl_csv_rows", default_value=4,
                                           min_value=1, max_value=30, width=120)
                        dpg.add_button(label="โหลด CSV → ข้อความ", callback=lambda: self.load_csv())
                    dpg.add_separator()
                    dpg.add_text("Before / After")
                    dpg.add_combo(
                        ["ค่าก่อนแก้ glyph vs ตอนนี้", "ไฟล์ต้นทาง vs ชุดแก้"],
                        default_value="ค่าก่อนแก้ glyph vs ตอนนี้",
                        tag="cmp_mode", width=280,
                        callback=lambda: self.queue_preview())
                    dpg.add_text("Before")
                    dpg.add_image(self._preview_a_tag)
                    dpg.add_text("After (ชุดแก้)")
                    dpg.add_image(self._preview_b_tag)
                    dpg.add_button(label="รีเฟรชพรีวิว", callback=lambda: self.refresh_preview())
                    dpg.add_text("", tag="lbl_status")
                    dpg.add_separator()
                    dpg.add_text("พรีวิวด้วย preset อ่านอย่างเดียว (ไม่สลับไฟล์แก้)")
                    dpg.add_combo(
                        list(FONT_PRESETS.keys()), default_value="dialog",
                        tag="cmb_preview_preset", width=160)
                    dpg.add_button(
                        label="เปิด preset เป็นไฟล์แก้ใหม่",
                        callback=lambda: self.load_font(
                            FONT_PRESETS[dpg.get_value("cmb_preview_preset")]))

        with dpg.file_dialog(
            directory_selector=False, show=False, tag="file_dialog",
            width=700, height=400, callback=self._on_file_picked,
        ):
            dpg.add_file_extension(".fnt", color=(200, 200, 100))

        dpg.create_viewport(title="ThaiFNV Font Workbench", width=1480, height=920)
        dpg.setup_dearpygui()
        dpg.set_primary_window("main", True)
        dpg.show_viewport()

        if self.initial_fnt.is_file():
            self.load_font(self.initial_fnt)
        else:
            dpg.set_value("lbl_status", "ไม่พบฟอนต์เริ่มต้น: %s" % self.initial_fnt)

        while dpg.is_dearpygui_running():
            self.tick_preview()
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

    def _open_file_dialog(self):
        dpg.show_item("file_dialog")

    def _on_file_picked(self, sender, app_data):
        selections = app_data.get("selections") or {}
        if not selections:
            return
        path = Path(next(iter(selections.values())))
        if path.suffix.lower() == ".fnt":
            self.load_font(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fnt", type=Path, default=None)
    args = ap.parse_args()
    wb = Workbench(args.fnt)
    wb.build()


if __name__ == "__main__":
    main()
