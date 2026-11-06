import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'd:\backup\github\ThaiFNV\pipeline')

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'd:\backup\github\ThaiFNV\pipeline')

from PIL import Image, ImageDraw, ImageFont
import font_builder
from fnt_lib import load_fnt, Glyph
from thai_shaper_engine import shape_thai_text
import os

ttf = r'd:\backup\github\ThaiFNV\fonts\src\Sarabun-Bold.ttf'

from font_builder import build_font
from fnt_lib import load_fnt
import os
import shutil

# Build test fonts with different baseline lifts
os.makedirs(r'd:\backup\github\ThaiFNV\fonts\out\test', exist_ok=True)

def build_and_render_comparison():
    lifts = [0.0, 4.0, 6.0, 7.0]
    canvas = Image.new('RGBA', (500, 320), (15, 12, 10, 255))
    y_cur = 20
    
    for lift in lifts:
        # We can temporarily patch or pass baseline_lift
        out_base = rf'd:\backup\github\ThaiFNV\fonts\out\test\test_lift_{int(lift)}'
        atlas, glyphs, line_h = build_font(
            ttf, "test", 18, out_base=out_base,
            line_height=32.0, target_ascent=23.0, outline=1, stroke_gap=0.5,
            baseline_lift=lift
        )
        
        # Render dialog box
        box_w, box_h = 460, int(line_h + 20)  # 52px
        box_img = Image.new('RGBA', (box_w, box_h), (25, 20, 15, 255))
        draw = ImageDraw.Draw(box_img)
        draw.rectangle([0, 0, box_w - 1, box_h - 1], outline=(220, 180, 80, 220), width=1)
        
        baseline = 15.0 + line_h
        text = "ขอบคุณที่ขุดฉันออกมาจากหลุมนั้น"
        shaped = shape_thai_text(text)
        
        pen_x = 25.0
        for code in shaped:
            g = glyphs[code]
            if g.px_width > 0 and g.px_height > 0:
                gx1 = int(round(g.uv_left * atlas.width))
                gy1 = int(round(g.uv_top * atlas.height))
                gx2 = int(round(g.uv_right * atlas.width))
                gy2 = int(round(g.uv_bottom * atlas.height))
                glyph_img = atlas.crop((gx1, gy1, gx2, gy2))
                
                dest_x = int(round(pen_x + g.bearing_x))
                dest_y = int(round(baseline - g.ascent))
                box_img.alpha_composite(glyph_img, (dest_x, dest_y))
            pen_x += g.advance
            
        canvas.paste(box_img, (20, y_cur))
        ld = ImageDraw.Draw(canvas)
        ld.text((20, y_cur - 12), f"baseline_lift = {lift}px", fill=(220, 200, 150, 255))
        y_cur += 75
        
    canvas.save(r'C:\Users\saetanpee\.gemini\antigravity\brain\5220f6a4-fb4b-462e-bb76-2d8317f76742\lift_test_ladder.png')
    print("Ladder saved!")


