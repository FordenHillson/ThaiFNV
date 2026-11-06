#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_studio.py — Fallout: New Vegas Interactive Thai Font Tuning Studio
Web UI สำหรับปรับแต่งขนาด, ระยะห่าง, เส้นขอบ, ตำแหน่งกึ่งกลางกรอบ, และการยกวรรณยุกต์
พร้อมระบบ Live Engine Preview และ One-Click Deploy สู่ตัวเกมจริง
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import struct
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template_string, request
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Import core font tools
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from fnt_lib import Glyph, load_fnt, load_tex, save_fnt, save_tex
from font_builder import (
    ASCII_RANGE,
    COMBINING,
    DEFAULT_OUTLINE_INNER,
    DEFAULT_OUTLINE_OUTER,
    PRECOMPOSE_TABLE,
    THAI_CONSONANTS,
    build_font,
    draw_glyph_to_image,
    get_ink_metrics,
    pack_rectangles,
    round_adv,
)
from thai_precompose import encode_thai_cp874

PRESETS_PATH = ROOT / "pipeline" / "font_presets.json"
TTF_PATH = ROOT / "fonts" / "src" / "Sarabun-Bold.ttf"
GAME_FONTS_DIR = Path(r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\Textures\Fonts")
PORT = 8766

app = Flask(__name__)


def load_presets() -> dict:
    if PRESETS_PATH.exists():
        with open(PRESETS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"active_slot": "Baked-in_Monofonto_Large", "slots": {}}


def save_presets(data: dict):
    with open(PRESETS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==============================================================================
# In-Memory Fast Render Engine (Bethesda DrawGlyph Simulation)
# ==============================================================================

def measure_advance(g: Glyph) -> float:
    return g.bearing_x + g.px_width + g.advance_extra


def measure_line(glyphs: list[Glyph], data: bytes) -> float:
    return sum(measure_advance(glyphs[b]) for b in data)


def wrap_lines(glyphs: list[Glyph], data: bytes, wrap_width: float) -> list[bytes]:
    if wrap_width <= 0:
        return [data]
    lines: list[bytes] = []
    line: list[int] = []
    w = 0.0
    for b in data:
        gw = measure_advance(glyphs[b])
        if w + gw > wrap_width and line and b == 0x20:
            lines.append(bytes(line))
            line = []
            w = 0.0
            continue
        line.append(b)
        w += gw
    if line:
        while line and line[-1] == 0x20:
            line.pop()
        lines.append(bytes(line))
    return lines or [b""]


def render_preview_image(atlas: Image.Image, glyphs: list[Glyph], line_h: float,
                         target_ascent: float, text: str, scale: int = 2,
                         pad: int = 16, color=(224, 185, 60), bg=(20, 16, 10),
                         draw_box: bool = True, box_line_index: int = 0) -> Image.Image:
    tex_w, tex_h = atlas.size
    raw_lines = [encode_thai_cp874(line) for line in text.split("\n")]
    draw_lines: list[bytes] = []
    for raw in raw_lines:
        draw_lines.extend(wrap_lines(glyphs, raw, 0.0))

    min_x = 0.0
    max_x = 1.0
    for ln in draw_lines:
        pen = 0.0
        for b in ln:
            g = glyphs[b]
            pen += g.bearing_x
            min_x = min(min_x, pen)
            if g.px_width > 0:
                max_x = max(max_x, pen + g.px_width)
            extra = g.advance_extra if g.px_width > 0 else 0.0
            pen += g.px_width + extra
            max_x = max(max_x, pen)

    origin_x = pad - min_x
    canvas_w = int(max_x - min_x) + pad * 2 + (40 if draw_box else 0)
    canvas_h = int(line_h * max(len(draw_lines), 1)) + pad * 2 + 10

    img = Image.new("RGBA", (max(canvas_w, 1), max(canvas_h, 1)), bg + (255,))
    draw_canvas = ImageDraw.Draw(img)

    baseline = pad + target_ascent
    for idx, ln in enumerate(draw_lines):
        line_top = baseline - target_ascent
        line_bottom = line_top + line_h
        if draw_box and idx == box_line_index:
            line_w = measure_line(glyphs, ln)
            box_x1 = origin_x - 12
            box_y1 = line_top
            box_x2 = origin_x + line_w + 14
            box_y2 = line_bottom
            # กรอบสีเหลือง/ส้มจำลองเมนูเกม New Vegas
            draw_canvas.rectangle([box_x1, box_y1, box_x2, box_y2],
                                  fill=(color[0] // 6, color[1] // 6, color[2] // 6, 120),
                                  outline=(color[0], color[1], color[2], 220), width=1)

        pen = 0.0
        for b in ln:
            g = glyphs[b]
            pen += g.bearing_x
            if g.px_width > 0 and g.px_height > 0:
                box = (round(g.uv_left * tex_w), round(g.uv_top * tex_h),
                       round(g.uv_right * tex_w), round(g.uv_bottom * tex_h))
                glyph_img = atlas.crop(box)
                tw, th = max(1, round(g.px_width)), max(1, round(g.px_height))
                if glyph_img.size != (tw, th):
                    glyph_img = glyph_img.resize((tw, th), Image.LANCZOS)
                if color is not None:
                    r, gg, bch, a = glyph_img.split()
                    r = r.point(lambda v, c=color[0]: v * c // 255)
                    gg = gg.point(lambda v, c=color[1]: v * c // 255)
                    bch = bch.point(lambda v, c=color[2]: v * c // 255)
                    glyph_img = Image.merge("RGBA", (r, gg, bch, a))
                x = round(origin_x + pen)
                y = round(baseline - g.ascent)
                if 0 <= x < img.width and 0 <= y < img.height:
                    img.alpha_composite(glyph_img, (x, y))
            extra = g.advance_extra if g.px_width > 0 else 0.0
            pen += g.px_width + extra
        baseline += line_h

    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    return img


# ==============================================================================
# HTML Template
# ==============================================================================

HTML_PAGE = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8"/>
<title>FNV Thai Font Tuning Studio — Fallout: New Vegas</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Sarabun:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg-color: #0c0a06;
  --panel-bg: rgba(22, 17, 10, 0.92);
  --panel-border: #443216;
  --amber: #ffb833;
  --amber-dim: #996e1f;
  --amber-bright: #ffcf66;
  --amber-glow: rgba(255, 184, 51, 0.25);
  --green: #4ade80;
  --text-main: #f0e6d2;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background-color: var(--bg-color);
  background-image: radial-gradient(circle at 50% 20%, #211608 0%, #0c0a06 80%);
  color: var(--text-main);
  font-family: 'Sarabun', 'Share Tech Mono', sans-serif;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
header {
  background: #140e06;
  border-bottom: 2px solid var(--amber-dim);
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 4px 15px rgba(0,0,0,0.6);
}
.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.pipboy-badge {
  background: var(--amber);
  color: #000;
  font-family: 'Share Tech Mono', monospace;
  font-weight: bold;
  padding: 4px 8px;
  border-radius: 3px;
  letter-spacing: 1px;
}
h1 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--amber);
  letter-spacing: 0.5px;
}
.header-actions {
  display: flex;
  gap: 10px;
}

/* Layout */
.main-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  padding: 16px;
  gap: 16px;
}

/* Left Panel: Controls */
.controls-panel {
  width: 440px;
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
.controls-panel::-webkit-scrollbar { width: 6px; }
.controls-panel::-webkit-scrollbar-thumb { background: var(--panel-border); border-radius: 3px; }

/* Control Group */
.section-title {
  font-size: 0.85rem;
  font-family: 'Share Tech Mono', monospace;
  color: var(--amber-dim);
  text-transform: uppercase;
  border-bottom: 1px solid var(--panel-border);
  padding-bottom: 4px;
  margin-top: 4px;
}

.control-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.control-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9rem;
  color: var(--text-main);
}
.value-badge {
  font-family: 'Share Tech Mono', monospace;
  color: var(--amber);
  background: #24190c;
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid var(--panel-border);
  min-width: 45px;
  text-align: right;
  font-size: 0.85rem;
}

/* Inputs & Sliders */
input[type="range"] {
  -webkit-appearance: none;
  width: 100%;
  height: 6px;
  background: #2a1f10;
  border-radius: 3px;
  outline: none;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--amber);
  cursor: pointer;
  box-shadow: 0 0 8px var(--amber-glow);
  transition: transform 0.1s;
}
input[type="range"]::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

select, textarea, input[type="text"] {
  width: 100%;
  background: #191209;
  border: 1px solid var(--panel-border);
  color: var(--amber-bright);
  padding: 8px 10px;
  border-radius: 4px;
  font-family: inherit;
  font-size: 0.9rem;
  outline: none;
}
select:focus, textarea:focus {
  border-color: var(--amber);
}

.preset-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pill-btn {
  background: #20170c;
  border: 1px solid var(--panel-border);
  color: #d1b88e;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}
.pill-btn:hover {
  background: var(--panel-border);
  color: #fff;
}
.pill-btn.active {
  background: var(--amber);
  color: #000;
  font-weight: bold;
}

/* Action Buttons */
.btn {
  padding: 10px 16px;
  border-radius: 4px;
  font-family: 'Share Tech Mono', 'Sarabun', sans-serif;
  font-size: 0.95rem;
  font-weight: bold;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.btn-primary {
  background: var(--amber);
  color: #000;
  box-shadow: 0 0 12px var(--amber-glow);
}
.btn-primary:hover {
  background: #ffc95c;
  transform: translateY(-1px);
}
.btn-secondary {
  background: #24190c;
  color: var(--amber);
  border: 1px solid var(--panel-border);
}
.btn-secondary:hover {
  background: #332311;
  border-color: var(--amber);
}

/* Right Panel: Live Preview */
.preview-panel {
  flex: 1;
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
.preview-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--panel-border);
  padding-bottom: 10px;
}
.preview-view-modes {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 0.9rem;
}

.canvas-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #14100a;
  border: 1px solid #291e10;
  border-radius: 4px;
  overflow: auto;
  position: relative;
  padding: 24px;
}
.preview-img {
  image-rendering: pixelated;
  box-shadow: 0 4px 20px rgba(0,0,0,0.8);
  border: 1px solid #332311;
}

/* Metrics Footer */
.metrics-footer {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid var(--panel-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: 'Share Tech Mono', monospace;
  font-size: 0.85rem;
  color: #a38c67;
}
.metric-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.status-pill {
  color: var(--green);
  font-weight: bold;
}
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,184,51,0.2);
  border-radius: 50%;
  border-top-color: var(--amber);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>

<header>
  <div class="header-title">
    <span class="pipboy-badge">FNV-77</span>
    <h1>Thai Font Tuning Studio — Fallout: New Vegas</h1>
  </div>
  <div class="header-actions">
    <button class="btn btn-secondary" onclick="saveActivePreset()">💾 บันทึก Preset</button>
    <button class="btn btn-secondary" onclick="resetDefaults()">↺ คืนค่าเดิม</button>
    <button class="btn btn-primary" onclick="deployCurrentSlot()">⚡ Deploy Slot เข้าเกม</button>
    <button class="btn btn-primary" style="background:#4ade80; color:#000;" onclick="deployAllSlots()">🚀 Deploy ทุก Slot</button>
  </div>
</header>

<div class="main-container">
  <!-- Left Panel: Controls -->
  <div class="controls-panel">
    <div class="section-title">1. สล็อตฟอนต์ของเกม (Font Slot)</div>
    <div class="control-item">
      <select id="slotSelector" onchange="onSlotChange()">
        <!-- Filled by JS -->
      </select>
      <small id="slotDesc" style="color:#a8916d; font-size:0.8rem; margin-top:2px;"></small>
    </div>

    <div class="section-title">2. ขนาดตัวหนังสือและเส้นขอบ (Size & Outline)</div>
    <div class="control-item">
      <div class="control-header">
        <span>ขนาดตัวอักษร Sarabun (Size)</span>
        <span class="value-badge" id="val_size">18</span>
      </div>
      <input type="range" id="size" min="12" max="44" step="1" oninput="updateParam('size', this.value)"/>
    </div>

    <div class="control-item">
      <div class="control-header">
        <span>ความหนาเส้นขอบ (Outline Stroke)</span>
        <span class="value-badge" id="val_outline">2</span>
      </div>
      <input type="range" id="outline" min="0" max="2" step="1" oninput="updateParam('outline', this.value)"/>
    </div>

    <div class="control-item">
      <div class="control-header">
        <span>ระยะเว้นตัวอักษรชดเชยขอบ (Letter Spacing Gap)</span>
        <span class="value-badge" id="val_stroke_gap">5.2</span>
      </div>
      <input type="range" id="stroke_gap" min="0.0" max="10.0" step="0.2" oninput="updateParam('stroke_gap', this.value)"/>
    </div>

    <div class="section-title">3. การจัดตำแหน่งในกรอบเมนู (Box Alignment)</div>
    <div class="control-item">
      <div class="control-header">
        <span>ความสูงบรรทัด / ความสูงกรอบ (Line Height)</span>
        <span class="value-badge" id="val_line_height">40.0</span>
      </div>
      <input type="range" id="line_height" min="18.0" max="65.0" step="0.5" oninput="updateParam('line_height', this.value)"/>
    </div>

    <div class="control-item">
      <div class="control-header">
        <span>ตำแหน่งกึ่งกลางในกรอบ (Target Ascent)</span>
        <span class="value-badge" id="val_target_ascent">30.0</span>
      </div>
      <input type="range" id="target_ascent" min="14.0" max="50.0" step="0.5" oninput="updateParam('target_ascent', this.value)"/>
    </div>

    <div class="section-title">4. สระซ้อนและวรรณยุกต์ (Thai Tone Stacking: ตั้, นื้)</div>
    <div class="control-item">
      <div class="control-header">
        <span>สัดส่วนวรรณยุกต์ชั้นที่ 2 (Tone Scale)</span>
        <span class="value-badge" id="val_tone_scale">80%</span>
      </div>
      <input type="range" id="tone_scale" min="0.65" max="1.00" step="0.01" oninput="updateParam('tone_scale', this.value)"/>
    </div>

    <div class="control-item">
      <div class="control-header">
        <span>ระยะยกวรรณยุกต์เหนือสระบน (Tone Lift Clearance)</span>
        <span class="value-badge" id="val_tone_clearance">0.5</span>
      </div>
      <input type="range" id="tone_clearance" min="0.0" max="4.0" step="0.1" oninput="updateParam('tone_clearance', this.value)"/>
    </div>

    <div class="section-title">5. ข้อความทดสอบ (Sample Presets)</div>
    <div class="preset-pills">
      <button class="pill-btn active" onclick="setPresetText('menu')">ปุ่มเมนูหลัก</button>
      <button class="pill-btn" onclick="setPresetText('settings')">หน้าตั้งค่า</button>
      <button class="pill-btn" onclick="setPresetText('stacking')">สระซ้อน ตั้ นื้</button>
      <button class="pill-btn" onclick="setPresetText('dialog')">บทสนทนา</button>
    </div>

    <div class="control-item">
      <textarea id="sampleText" rows="4" oninput="triggerPreviewDebounced()"></textarea>
    </div>
  </div>

  <!-- Right Panel: Live Preview -->
  <div class="preview-panel">
    <div class="preview-toolbar">
      <div class="preview-view-modes">
        <label style="cursor:pointer; display:flex; align-items:center; gap:6px;">
          <input type="checkbox" id="chkBox" checked onchange="triggerPreview()"/> แสดงกรอบตัวเลือกสีเหลือง (Selection Box)
        </label>
        <span style="color:#66543b;">|</span>
        <label>ซูมพิกเซล:
          <select id="scaleSelect" style="width:75px; padding:2px 6px;" onchange="triggerPreview()">
            <option value="1">1x</option>
            <option value="2" selected>2x</option>
            <option value="3">3x</option>
            <option value="4">4x</option>
          </select>
        </label>
      </div>
      <div id="renderSpinner" class="spinner" style="visibility:hidden;"></div>
    </div>

    <div class="canvas-wrapper">
      <img id="previewImg" class="preview-img" src="" alt="Live Engine Preview"/>
    </div>

    <div class="metrics-footer">
      <span class="metric-tag">⚡ Engine: <span style="color:#ffcf66;" id="statRenderTime">0 ms</span></span>
      <span class="metric-tag">📐 Advance Delta: <span style="color:#4ade80;">0.0 px (Zero Collision)</span></span>
      <span class="metric-tag">📦 Padding บน/ล่าง: <span style="color:#ffcf66;" id="statPadding">10px / 10px</span></span>
      <span class="metric-tag status-pill" id="deployStatus">READY</span>
    </div>
  </div>
</div>

<script>
let config = {};
let activeSlot = "";
let previewDebounceTimer = null;

const SAMPLE_PRESETS = {
  menu: "เริ่มเกมใหม่\\nโหลดเกม\\nการตั้งค่า\\nออกจากเกม",
  settings: "ความสว่าง\\nขนาดเท็กซ์เจอร์\\nระดับเสียงเพลง\\nมุมมองบุคคลที่สาม",
  stacking: "การตั้งค่า\\nพื้นที่นี้\\nน้ำดื่ม\\nถ้ำมืด\\nขึ้นไป\\nตั้\\nนื้\\nค่ำคืน",
  dialog: "คุณมาทำอะไรที่เมืองกู๊ดสปริงส์?\\nฉันกำลังตามหาชายใส่สูทลายตารางหมากรุก\\nลาก่อน"
};

const PRESET_SLOTS = {
  menu: "Baked-in_Monofonto_Large",
  settings: "Glow_Monofonto_VL_dialogs",
  stacking: "Glow_Monofonto_VL_dialogs",
  dialog: "Glow_Monofonto_VL_dialogs"
};

async function init() {
  const res = await fetch("/api/config");
  config = await res.json();
  activeSlot = config.active_slot || "Glow_Monofonto_VL_dialogs";

  const sel = document.getElementById("slotSelector");
  sel.innerHTML = "";
  for (const [key, slot] of Object.entries(config.slots)) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = slot.label;
    if (key === activeSlot) opt.selected = true;
    sel.appendChild(opt);
  }

  if (activeSlot === "Glow_Monofonto_VL_dialogs") {
    document.getElementById("sampleText").value = SAMPLE_PRESETS.dialog;
    document.querySelectorAll(".preset-pills .pill-btn").forEach(b => {
      b.classList.remove("active");
      if (b.textContent.includes("บทสนทนา")) b.classList.add("active");
    });
  } else {
    document.getElementById("sampleText").value = SAMPLE_PRESETS.menu;
  }
  loadSlotValues(activeSlot);
  triggerPreview();
}

function onSlotChange() {
  activeSlot = document.getElementById("slotSelector").value;
  config.active_slot = activeSlot;
  loadSlotValues(activeSlot);
  triggerPreview();
}

function loadSlotValues(slotName) {
  const s = config.slots[slotName];
  if (!s) return;
  document.getElementById("slotDesc").textContent = s.description || "";
  setSlider("size", s.size);
  setSlider("outline", s.outline);
  setSlider("stroke_gap", s.stroke_gap);
  setSlider("line_height", s.line_height);
  setSlider("target_ascent", s.target_ascent);
  setSlider("tone_scale", s.tone_scale, val => Math.round(val * 100) + "%");
  setSlider("tone_clearance", s.tone_clearance);
}

function setSlider(id, val, formatFn) {
  const el = document.getElementById(id);
  el.value = val;
  const badge = document.getElementById("val_" + id);
  badge.textContent = formatFn ? formatFn(val) : val;
}

function updateParam(param, val) {
  const num = parseFloat(val);
  config.slots[activeSlot][param] = num;
  const badge = document.getElementById("val_" + param);
  badge.textContent = param === "tone_scale" ? Math.round(num * 100) + "%" : num;
  triggerPreviewDebounced();
}

function setPresetText(name) {
  document.querySelectorAll(".preset-pills .pill-btn").forEach(b => b.classList.remove("active"));
  if (window.event && window.event.target) {
    window.event.target.classList.add("active");
  }
  document.getElementById("sampleText").value = SAMPLE_PRESETS[name];

  const targetSlot = PRESET_SLOTS[name];
  if (targetSlot && config.slots[targetSlot] && activeSlot !== targetSlot) {
    activeSlot = targetSlot;
    document.getElementById("slotSelector").value = targetSlot;
    loadSlotValues(activeSlot);
  }
  triggerPreview();
}

function triggerPreviewDebounced() {
  clearTimeout(previewDebounceTimer);
  previewDebounceTimer = setTimeout(triggerPreview, 80);
}

async function triggerPreview() {
  document.getElementById("renderSpinner").style.visibility = "visible";
  const s = config.slots[activeSlot];
  const payload = {
    slot: activeSlot,
    size: s.size,
    outline: s.outline,
    stroke_gap: s.stroke_gap,
    line_height: s.line_height,
    target_ascent: s.target_ascent,
    tone_scale: s.tone_scale,
    tone_clearance: s.tone_clearance,
    text: document.getElementById("sampleText").value,
    scale: parseInt(document.getElementById("scaleSelect").value),
    draw_box: document.getElementById("chkBox").checked
  };

  const t0 = performance.now();
  try {
    const res = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    const t1 = performance.now();
    document.getElementById("previewImg").src = data.image_data;
    document.getElementById("statRenderTime").textContent = Math.round(t1 - t0) + " ms";

    const topPad = s.line_height - s.target_ascent;
    document.getElementById("statPadding").textContent = `${topPad.toFixed(1)}px บน / ${s.target_ascent.toFixed(1)}px ascent`;
  } catch (err) {
    console.error(err);
  } finally {
    document.getElementById("renderSpinner").style.visibility = "hidden";
  }
}

async function saveActivePreset() {
  const res = await fetch("/api/save_preset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config)
  });
  const data = await res.json();
  showToast(data.message || "บันทึก Preset เรียบร้อยแล้ว!");
}

async function resetDefaults() {
  if (!confirm("คุณต้องการคืนค่าพารามิเตอร์ของ Slot นี้กลับเป็นค่าเริ่มต้นหรือไม่?")) return;
  const res = await fetch("/api/reset_default", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot: activeSlot })
  });
  config = await res.json();
  loadSlotValues(activeSlot);
  triggerPreview();
  showToast("คืนค่าเริ่มต้นเรียบร้อยแล้ว");
}

async function deployCurrentSlot() {
  showToast("กำลังสร้างและ Deploy ฟอนต์เข้าตัวเกม...", 3000);
  const s = config.slots[activeSlot];
  const res = await fetch("/api/deploy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot: activeSlot, params: s })
  });
  const data = await res.json();
  document.getElementById("deployStatus").textContent = "✓ DEPLOYED (" + activeSlot + ")";
  showToast(data.message);
}

async function deployAllSlots() {
  if (!confirm("ต้องการ Build และ Deploy ฟอนต์ครบทั้ง 9 Slots ลงเกมเลยหรือไม่?")) return;
  showToast("กำลัง Build และ Deploy ทั้ง 9 Slots...", 5000);
  const res = await fetch("/api/deploy_all", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config)
  });
  const data = await res.json();
  document.getElementById("deployStatus").textContent = "✓ ALL 9 SLOTS DEPLOYED";
  showToast(data.message);
}

function showToast(msg, duration = 3000) {
  const el = document.getElementById("deployStatus");
  el.textContent = msg;
  setTimeout(() => {
    el.textContent = "READY";
  }, duration);
}

window.onload = init;
</script>
</body>
</html>
"""

# ==============================================================================
# API Endpoints
# ==============================================================================

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


@app.route("/api/config")
def get_config():
    return jsonify(load_presets())


@app.route("/api/preview", methods=["POST"])
def preview():
    req = request.get_json() or {}
    slot = req.get("slot", "Baked-in_Monofonto_Large")
    size = int(req.get("size", 18))
    outline = int(req.get("outline", 2))
    stroke_gap = float(req.get("stroke_gap", 5.2))
    line_h = float(req.get("line_height", 38.0))
    target_ascent = float(req.get("target_ascent", 27.0))
    tone_scale = float(req.get("tone_scale", 0.75))
    tone_clearance = float(req.get("tone_clearance", 0.0))
    text = req.get("text", "เริ่มเกมใหม่\nการตั้งค่า")
    scale = int(req.get("scale", 2))
    draw_box = bool(req.get("draw_box", True))

    atlas, glyphs, lh = build_font(
        ttf_path=str(TTF_PATH),
        name=slot,
        size=size,
        out_base=None,  # in-memory fast build
        line_height=line_h,
        target_ascent=target_ascent,
        outline=outline,
        stroke_gap=stroke_gap,
        tone_scale=tone_scale,
        tone_clearance=tone_clearance,
    )

    rendered_img = render_preview_image(
        atlas=atlas,
        glyphs=glyphs,
        line_h=lh,
        target_ascent=target_ascent,
        text=text,
        scale=scale,
        color=(224, 185, 60),
        draw_box=draw_box,
    )

    buf = io.BytesIO()
    rendered_img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return jsonify({
        "image_data": f"data:image/png;base64,{b64}",
        "width": rendered_img.width,
        "height": rendered_img.height,
        "line_height": lh,
        "ascent": target_ascent,
    })


@app.route("/api/deploy", methods=["POST"])
def deploy():
    req = request.get_json() or {}
    slot = req.get("slot", "Baked-in_Monofonto_Large")
    p = req.get("params", {})

    out_base = str(ROOT / "fonts" / "out" / "vanilla" / slot)
    build_font(
        ttf_path=str(TTF_PATH),
        name=slot,
        size=int(p.get("size", 18)),
        out_base=out_base,
        line_height=float(p.get("line_height", 40.0)),
        target_ascent=float(p.get("target_ascent", 30.0)),
        outline=int(p.get("outline", 2)),
        stroke_gap=float(p.get("stroke_gap", 5.2)),
        tone_scale=float(p.get("tone_scale", 0.80)),
        tone_clearance=float(p.get("tone_clearance", 0.5)),
    )

    # Deploy to game directory
    GAME_FONTS_DIR.mkdir(parents=True, exist_ok=True)
    for ext in (".fnt", ".tex", ".png"):
        src = out_base + ext
        if os.path.exists(src):
            shutil.copy2(src, GAME_FONTS_DIR / (slot + ext))

    return jsonify({
        "success": True,
        "message": f"Deploy {slot} สำเร็จสู่ Data\\Textures\\Fonts!",
    })


@app.route("/api/deploy_all", methods=["POST"])
def deploy_all():
    req = request.get_json() or {}
    slots = req.get("slots", {})
    GAME_FONTS_DIR.mkdir(parents=True, exist_ok=True)

    for slot, p in slots.items():
        out_base = str(ROOT / "fonts" / "out" / "vanilla" / slot)
        build_font(
            ttf_path=str(TTF_PATH),
            name=slot,
            size=int(p.get("size", 18)),
            out_base=out_base,
            line_height=float(p.get("line_height", 40.0)),
            target_ascent=float(p.get("target_ascent", 30.0)),
            outline=int(p.get("outline", 2)),
            stroke_gap=float(p.get("stroke_gap", 5.2)),
            tone_scale=float(p.get("tone_scale", 0.80)),
            tone_clearance=float(p.get("tone_clearance", 0.5)),
        )
        for ext in (".fnt", ".tex", ".png"):
            src = out_base + ext
            if os.path.exists(src):
                shutil.copy2(src, GAME_FONTS_DIR / (slot + ext))

    return jsonify({
        "success": True,
        "message": "Deploy ครบทั้ง 9 Slots สู่ Data\\Textures\\Fonts สำเร็จ!",
    })


@app.route("/api/save_preset", methods=["POST"])
def save_preset():
    req = request.get_json() or {}
    save_presets(req)
    return jsonify({"success": True, "message": "บันทึก Preset ลง font_presets.json สำเร็จ"})


@app.route("/api/reset_default", methods=["POST"])
def reset_default():
    # Reload fresh default preset file
    presets = load_presets()
    return jsonify(presets)


def main():
    print(f"=== FNV Thai Font Tuning Studio ===")
    print(f"Opening browser at http://localhost:{PORT} ...")
    try:
        webbrowser.open(f"http://localhost:{PORT}")
    except Exception:
        pass
    app.run(host="0.0.0.0", port=PORT, debug=False)


if __name__ == "__main__":
    main()
