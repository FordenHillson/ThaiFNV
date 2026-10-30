#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_workbench.py — GUI จูนค่า Message Menu (message_menu.xml)

สูตรจาก REA / Capstone บน Tools/FalloutNV_unpacked.exe:

  0x71AD30 — เขียนทับ _scroll_delta เมื่อมีมากกว่า 1 แถว:
      scroll_delta = (list_height - item_height) / (n - 1)
    ถ้า list_height = n * item_height → scroll_delta = item_height

  0x7269D0 — ถ้าความสูงแถวใน XML ≠ 0 เกมอาจคำนวณใหม่จาก
      item_height ≈ metrics ฟอนต์ปุ่ม + _VerticalSpacing
    แล้ว set trait height (0xFB0)

จูนหลัก: ความสูงแถว (= _scroll_delta) + แถวที่เห็น + VerticalSpacing
list height ใน XML = visible × scroll_delta เพื่อให้สมการด้านบนคงที่

Usage:
  python ui_workbench.py
  python ui_workbench.py --xml "...\\Data\\Menus\\message_menu.xml"
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import dearpygui.dearpygui as dpg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
UI_FONT = ROOT / "fonts" / "src" / "Sarabun-Regular.ttf"
DEFAULT_GAME_XML = Path(
    r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\Menus\message_menu.xml"
)
PROJECT_XML = ROOT / "Data" / "Menus" / "message_menu.xml"
VORTEX_XML = Path(
    r"D:\Vortex Mods\falloutnv\Unofficial DarNified UI 93955 1.6 2026-09-23T23-45Z H1QaWJr5"
    r"\menus\message_menu.xml"
)

PREVIEW_W = 420
PREVIEW_H = 320


@dataclass
class MsgMenuTuning:
    max_menu_width: int = 780
    horbuf: int = 30
    verbuf: int = 44
    visible_rows: int = 4  # _number_of_visible_items
    row_height: int = 58   # ความสูงแถวปุ่ม — ตัวคุมระยะจริง
    vertical_spacing: int = 22
    gap_text_buttons: int = 52
    bottom_pad: int = 28
    title_y: int = -4

    @property
    def scroll_delta(self) -> int:
        """ค่าที่เกมจะได้เมื่อ list_h = visible * row (สูตร REA 0x71AD30)"""
        return int(self.row_height)

    @property
    def list_height(self) -> int:
        return int(self.visible_rows) * int(self.row_height)


# (attribute, regex to capture integer value, write format uses {v})
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "max_menu_width",
        re.compile(r"(<_MaxMenuWidth>)\s*(-?\d+)\s*(</_MaxMenuWidth>)"),
        r"\g<1> {v} \g<3>",
    ),
    (
        "horbuf",
        re.compile(r"(<_horbuf>)\s*(-?\d+)\s*(</_horbuf>)"),
        r"\g<1> {v} \g<3>",
    ),
    (
        "verbuf",
        re.compile(r"(<_verbuf>)\s*(-?\d+)\s*(</_verbuf>)"),
        r"\g<1> {v} \g<3>",
    ),
    (
        "visible_rows",
        re.compile(
            r'(<hotrect name="MM_ButtonList">[\s\S]*?<_number_of_visible_items>)\s*(-?\d+)\s*'
            r"(</_number_of_visible_items>)"
        ),
        r"\g<1> {v} \g<3>",
    ),
    (
        "scroll_delta",
        re.compile(
            r'(<hotrect name="MM_ButtonList">[\s\S]*?<_scroll_delta>)\s*(-?\d+)\s*(</_scroll_delta>)'
        ),
        r"\g<1> {v} \g<3>",
    ),
    (
        "gap_text_buttons",
        re.compile(
            r'(<hotrect name="MM_ButtonList">[\s\S]*?<add>)\s*(-?\d+)\s*(</add>\s*'
            r'<onlyif src="sibling\(MM_MessageText\)" trait="string"/>)'
        ),
        r"\g<1> {v} \g<3>",
    ),
    (
        "bottom_pad",
        re.compile(
            r'(<rect name="MM_BottomBracket">[\s\S]*?<add src="io\(\)" trait="_verbuf"/>\s*'
            r"<add>)\s*(-?\d+)\s*(</add>)"
        ),
        r"\g<1> {v} \g<3>",
    ),
    (
        "title_y",
        re.compile(
            r'(<text name="MM_Title">[\s\S]*?<y>)\s*(-?\d+)\s*(</y>)'
        ),
        r"\g<1> {v} \g<3>",
    ),
    (
        "vertical_spacing",
        re.compile(
            r'(<hotrect name="MM_Button">[\s\S]*?<_VerticalSpacing>)\s*(-?\d+)\s*'
            r"(</_VerticalSpacing>)"
        ),
        r"\g<1> {v} \g<3>",
    ),
    (
        "row_height",
        re.compile(
            r'(<hotrect name="MM_Button">[\s\S]*?<height>\s*<copy>)\s*(-?\d+)\s*(</copy>)'
        ),
        r"\g<1> {v} \g<3>",
    ),
]


def ensure_scroll_traits(text: str) -> str:
    """ใส่ _number_of_visible_items ใน MM_ButtonList ถ้ายังไม่มี + ใช้ height = visible×scroll"""
    out = text
    if "_number_of_visible_items" not in out.split("MM_ButtonList", 1)[-1][:800]:
        out = out.replace(
            '<hotrect name="MM_ButtonList">\n\t\t\t\t<include src="list_box.xml" />\n'
            "\t\t\t\t<id> 4 </id>",
            '<hotrect name="MM_ButtonList">\n\t\t\t\t<include src="list_box.xml" />\n'
            "\t\t\t\t<id> 4 </id>\n"
            "\t\t\t\t<_number_of_visible_items> 4 </_number_of_visible_items>",
            1,
        )
        # รูปแบบ include ไม่มีช่องว่างก่อน /
        if "_number_of_visible_items" not in out.split("MM_ButtonList", 1)[-1][:800]:
            out = out.replace(
                '<hotrect name="MM_ButtonList">\n\t\t\t\t<include src="list_box.xml"/>\n'
                "\t\t\t\t<id> 4 </id>",
                '<hotrect name="MM_ButtonList">\n\t\t\t\t<include src="list_box.xml"/>\n'
                "\t\t\t\t<id> 4 </id>\n"
                "\t\t\t\t<_number_of_visible_items> 4 </_number_of_visible_items>",
                1,
            )
    # height ของ list: ใช้จำนวนแถวที่เห็น ไม่ใช่จำนวนปุ่มทั้งหมด
    out = re.sub(
        r'(<hotrect name="MM_ButtonList">[\s\S]*?<height>)\s*'
        r'<copy src="child\(lb_scrollbar\)" trait="_number_of_items"/>\s*'
        r'<mul src="me\(\)" trait="_scroll_delta"/>\s*(</height>)',
        r'\1\n\t\t\t\t\t<copy src="me()" trait="_number_of_visible_items"/>\n'
        r'\t\t\t\t\t<mul src="me()" trait="_scroll_delta"/>\n\t\t\t\t\2',
        out,
        count=1,
    )
    return out


def load_tuning(path: Path) -> MsgMenuTuning:
    text = path.read_text(encoding="utf-8")
    t = MsgMenuTuning()
    for attr, pat, _fmt in PATTERNS:
        if attr == "scroll_delta":
            continue  # คำนวณจาก row_height ตามสูตรเกม
        m = pat.search(text)
        if m:
            setattr(t, attr, int(m.group(2)))
    return t


def apply_tuning(text: str, t: MsgMenuTuning) -> str:
    out = ensure_scroll_traits(text)
    for attr, pat, fmt in PATTERNS:
        val = t.scroll_delta if attr == "scroll_delta" else getattr(t, attr)
        if not pat.search(out):
            raise ValueError("ไม่พบแพทเทิร์นสำหรับ %s ใน XML" % attr)
        out = pat.sub(fmt.format(v=val), out, count=1)
    return out


def write_xml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.replace(path)
    except OSError:
        # ไฟล์ถูกล็อก — ลอง rename เดิมออกก่อน
        bak = path.with_suffix(path.suffix + ".bak")
        try:
            if path.exists():
                path.replace(bak)
            tmp.replace(path)
            if bak.exists():
                bak.unlink(missing_ok=True)
        except OSError as e:
            sidecar = path.with_suffix(path.suffix + ".new")
            shutil.copy2(tmp, sidecar)
            tmp.unlink(missing_ok=True)
            raise OSError("เขียน %s ไม่ได้ (ล็อก) — เซฟที่ %s แทน: %s" % (path, sidecar, e))


class UIWorkbench:
    def __init__(self, xml_path: Path):
        self.xml_path = xml_path
        self.raw = ""
        self.tuning = MsgMenuTuning()
        self.status = ""
        self._preview_draw = None

    def load(self) -> None:
        if not self.xml_path.exists():
            raise FileNotFoundError(self.xml_path)
        self.raw = self.xml_path.read_text(encoding="utf-8")
        self.tuning = load_tuning(self.xml_path)
        self.status = "โหลดแล้ว: %s" % self.xml_path

    def read_ui(self) -> MsgMenuTuning:
        return MsgMenuTuning(
            max_menu_width=int(dpg.get_value("sl_max_w")),
            horbuf=int(dpg.get_value("sl_horbuf")),
            verbuf=int(dpg.get_value("sl_verbuf")),
            visible_rows=int(dpg.get_value("sl_visible")),
            row_height=int(dpg.get_value("sl_row")),
            vertical_spacing=int(dpg.get_value("sl_vspace")),
            gap_text_buttons=int(dpg.get_value("sl_gap")),
            bottom_pad=int(dpg.get_value("sl_bottom")),
            title_y=int(dpg.get_value("sl_title_y")),
        )

    def push_ui(self) -> None:
        t = self.tuning
        dpg.set_value("sl_max_w", t.max_menu_width)
        dpg.set_value("sl_horbuf", t.horbuf)
        dpg.set_value("sl_verbuf", t.verbuf)
        dpg.set_value("sl_visible", t.visible_rows)
        dpg.set_value("sl_row", t.row_height)
        dpg.set_value("sl_vspace", t.vertical_spacing)
        dpg.set_value("sl_gap", t.gap_text_buttons)
        dpg.set_value("sl_bottom", t.bottom_pad)
        dpg.set_value("sl_title_y", t.title_y)
        dpg.set_value("txt_scroll_info", self._scroll_info(t))
        dpg.set_value("txt_status", self.status)
        self.redraw_preview()

    @staticmethod
    def _scroll_info(t: MsgMenuTuning) -> str:
        return (
            "REA 0x71AD30: _scroll_delta≈%d | list_h=%d (%d×%d)\n"
            "REA 0x7269D0: item อาจเป็นฟอนต์+VerticalSpacing(%d)"
            % (
                t.scroll_delta,
                t.list_height,
                t.visible_rows,
                t.row_height,
                t.vertical_spacing,
            )
        )

    def on_change(self, _sender=None, _app_data=None) -> None:
        self.tuning = self.read_ui()
        dpg.set_value("txt_scroll_info", self._scroll_info(self.tuning))
        self.redraw_preview()

    def redraw_preview(self) -> None:
        t = self.tuning
        if not dpg.does_item_exist("preview_layer"):
            return
        dpg.delete_item("preview_layer", children_only=True)
        # พื้นกล่อง
        pad = 16
        box_x, box_y = 20, 20
        box_w = PREVIEW_W - 40
        # หัว + เนื้อคร่าว ๆ
        dpg.draw_rectangle(
            (box_x, box_y), (box_x + box_w, box_y + PREVIEW_H - 40),
            color=(224, 185, 60, 255), fill=(20, 16, 10, 220),
            parent="preview_layer", thickness=1,
        )
        dpg.draw_text(
            (box_x + pad, box_y + 10 + t.title_y),
            "หัวข้อกล่องข้อความ",
            size=16, color=(224, 185, 60, 255), parent="preview_layer",
        )
        body_y = box_y + 36 + max(0, t.verbuf // 4)
        for i, line in enumerate(("บรรทัดเนื้อหา 1", "บรรทัดเนื้อหา 2", "บรรทัดเนื้อหา 3")):
            dpg.draw_text(
                (box_x + pad, body_y + i * 18),
                line, size=14, color=(210, 180, 90, 255), parent="preview_layer",
            )
        # ตัวเลือก — ระยะตามสูตรเกม: step = scroll_delta ≈ row_height
        opt_y = body_y + 3 * 18 + max(8, t.gap_text_buttons // 3)
        opts = (
            "ปล่อยมันไว้เฉยๆ",
            "ลองซ่อมโดยไม่ต้องใช้ชิ้นส่วน",
            "ตรวจสอบอุปกรณ์",
            "(วิทยาศาสตร์)",
            "ตัวเลือกที่ 5",
        )
        step = t.scroll_delta
        view_h = t.list_height
        dpg.draw_rectangle(
            (box_x + 28, opt_y - 2),
            (box_x + box_w - 12, opt_y + view_h + 2),
            color=(120, 90, 40, 200), fill=(30, 22, 12, 100),
            parent="preview_layer", thickness=1,
        )
        visible = opts[: max(1, t.visible_rows)]
        for i, label in enumerate(visible):
            y = opt_y + i * step
            dpg.draw_rectangle(
                (box_x + 40, y),
                (box_x + box_w - 36, y + t.row_height),
                color=(180, 140, 40, 180) if i == 0 else (80, 60, 30, 120),
                fill=(60, 40, 15, 80) if i == 0 else (0, 0, 0, 0),
                parent="preview_layer", thickness=1,
            )
            ty = y + max(0, (t.row_height - 16) // 2)
            dpg.draw_text(
                (box_x + 50, ty), label, size=15,
                color=(224, 185, 60, 255), parent="preview_layer",
            )
        if len(opts) > t.visible_rows:
            ax = box_x + 32
            dpg.draw_triangle(
                (ax, opt_y + 6), (ax + 8, opt_y + 6), (ax + 4, opt_y + 1),
                color=(224, 185, 60, 255), fill=(224, 185, 60, 255),
                parent="preview_layer",
            )
            by = opt_y + view_h - 8
            dpg.draw_triangle(
                (ax, by), (ax + 8, by), (ax + 4, by + 5),
                color=(224, 185, 60, 255), fill=(224, 185, 60, 255),
                parent="preview_layer",
            )
        bottom_y = opt_y + view_h + max(4, t.bottom_pad // 2)
        dpg.draw_line(
            (box_x, min(bottom_y, box_y + PREVIEW_H - 50)),
            (box_x + box_w, min(bottom_y, box_y + PREVIEW_H - 50)),
            color=(224, 185, 60, 255), parent="preview_layer", thickness=1,
        )
        dpg.draw_text(
            (box_x + pad, PREVIEW_H - 28),
            "visible=%d  row=%d  scroll≈%d  list_h=%d" % (
                t.visible_rows, t.row_height, t.scroll_delta, t.list_height),
            size=13, color=(180, 160, 120, 255), parent="preview_layer",
        )

    def apply(self, also_project: bool = True, also_vortex: bool = True) -> None:
        self.tuning = self.read_ui()
        try:
            new_text = apply_tuning(self.raw, self.tuning)
        except ValueError as e:
            self.status = "ผิดพลาด: %s" % e
            dpg.set_value("txt_status", self.status)
            return
        targets = [self.xml_path]
        if also_project:
            targets.append(PROJECT_XML)
        if also_vortex and VORTEX_XML.parent.exists():
            targets.append(VORTEX_XML)
        ok, fail = [], []
        for p in targets:
            try:
                write_xml(p, new_text)
                ok.append(str(p))
            except OSError as e:
                fail.append(str(e))
        self.raw = new_text
        self.status = "บันทึกแล้ว %d ไฟล์" % len(ok)
        if fail:
            self.status += " | " + "; ".join(fail)
        dpg.set_value("txt_status", self.status)
        self.redraw_preview()

    def reload(self) -> None:
        try:
            self.load()
            self.push_ui()
        except Exception as e:
            self.status = "โหลดไม่สำเร็จ: %s" % e
            dpg.set_value("txt_status", self.status)

    def build(self) -> None:
        dpg.create_context()
        with dpg.font_registry():
            if UI_FONT.exists():
                with dpg.font(str(UI_FONT), 18) as thai_font:
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Thai)
                dpg.bind_font(thai_font)

        with dpg.window(label="ThaiFNV UI Workbench — Message Menu", tag="main",
                        width=920, height=640):
            dpg.add_text("ไฟล์: ")
            dpg.add_input_text(tag="txt_path", default_value=str(self.xml_path), width=700)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Reload", callback=lambda: self._reload_path())
                dpg.add_button(label="Apply → เกม", callback=lambda: self.apply(True, True))

            with dpg.group(horizontal=True):
                with dpg.child_window(width=420, height=540):
                    dpg.add_text("ค่าที่จูนได้ (สูตรยืนยันด้วย REA)")
                    dpg.add_slider_int(
                        label="ความสูงแถว / scroll_delta", tag="sl_row",
                        default_value=58, min_value=24, max_value=120,
                        callback=self.on_change, width=280)
                    dpg.add_slider_int(
                        label="VerticalSpacing (+ฟอนต์)", tag="sl_vspace",
                        default_value=22, min_value=0, max_value=80,
                        callback=self.on_change, width=280)
                    dpg.add_slider_int(
                        label="แถวที่เห็นก่อนเลื่อน", tag="sl_visible",
                        default_value=4, min_value=1, max_value=8,
                        callback=self.on_change, width=280)
                    dpg.add_text("", tag="txt_scroll_info", wrap=380)
                    dpg.add_separator()
                    dpg.add_slider_int(label="verbuf (ขอบบน/ล่าง)", tag="sl_verbuf",
                                       default_value=44, min_value=10, max_value=80,
                                       callback=self.on_change, width=280)
                    dpg.add_slider_int(label="ช่องว่าง เนื้อ↔ปุ่ม", tag="sl_gap",
                                       default_value=52, min_value=10, max_value=100,
                                       callback=self.on_change, width=280)
                    dpg.add_slider_int(label="bottom pad", tag="sl_bottom",
                                       default_value=28, min_value=0, max_value=60,
                                       callback=self.on_change, width=280)
                    dpg.add_slider_int(label="title y", tag="sl_title_y",
                                       default_value=-4, min_value=-30, max_value=20,
                                       callback=self.on_change, width=280)
                    dpg.add_slider_int(label="MaxMenuWidth", tag="sl_max_w",
                                       default_value=780, min_value=400, max_value=1000,
                                       callback=self.on_change, width=280)
                    dpg.add_slider_int(label="horbuf", tag="sl_horbuf",
                                       default_value=30, min_value=10, max_value=80,
                                       callback=self.on_change, width=280)
                    dpg.add_spacer(height=8)
                    dpg.add_text("", tag="txt_status", wrap=380)

                with dpg.child_window(width=PREVIEW_W + 20, height=PREVIEW_H + 40):
                    dpg.add_text("พรีวิว (list_h = แถวที่เห็น × ความสูงแถว)")
                    with dpg.drawlist(width=PREVIEW_W, height=PREVIEW_H, tag="preview_dl"):
                        with dpg.draw_layer(tag="preview_layer"):
                            pass

            dpg.add_text(
                "REA: scroll_delta = (list_h − item_h)/(n−1) @0x71AD30 · "
                "item_h อาจ = ฟอนต์ + VerticalSpacing @0x7269D0 · "
                "จูนแถว+spacing ให้สอดคล้องกัน · หลัง Apply ปิดเกมเปิดใหม่",
                wrap=880,
            )

        dpg.create_viewport(title="ThaiFNV UI Workbench", width=940, height=680)
        dpg.setup_dearpygui()
        dpg.set_primary_window("main", True)
        self.push_ui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()

    def _reload_path(self) -> None:
        self.xml_path = Path(dpg.get_value("txt_path"))
        self.reload()


def main() -> None:
    ap = argparse.ArgumentParser(description="จูน message_menu.xml")
    ap.add_argument("--xml", type=Path, default=DEFAULT_GAME_XML,
                    help="พาธ message_menu.xml หลัก")
    args = ap.parse_args()
    app = UIWorkbench(args.xml)
    try:
        app.load()
    except FileNotFoundError:
        # fallback โปรเจกต์
        if PROJECT_XML.exists():
            app.xml_path = PROJECT_XML
            app.load()
        else:
            print("ไม่พบ message_menu.xml — ระบุ --xml")
            sys.exit(1)
    app.build()


if __name__ == "__main__":
    main()
