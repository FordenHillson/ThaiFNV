import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'd:\backup\github\ThaiFNV\pipeline')

from PIL import Image, ImageDraw, ImageFont
from font_builder import build_font
from thai_shaper_engine import shape_thai_text

ttf = r'd:\backup\github\ThaiFNV\fonts\src\Sarabun-Bold.ttf'

# Build font with lift=0 and lift=8
atlas0, glyphs0, lh0 = build_font(ttf, 'test0', 18, line_height=32.0, outline=1, stroke_gap=0.5, baseline_lift=0.0)
atlas8, glyphs8, lh8 = build_font(ttf, 'test8', 18, line_height=32.0, outline=1, stroke_gap=0.5, baseline_lift=8.0)

# Also for font size 17 (Monofonto_Large used in buttons and tabs)
atlas_m0, glyphs_m0, lh_m0 = build_font(ttf, 'test_m0', 17, line_height=31.0, outline=1, stroke_gap=0.5, baseline_lift=0.0)
atlas_m8, glyphs_m8, lh_m8 = build_font(ttf, 'test_m8', 17, line_height=31.0, outline=1, stroke_gap=0.5, baseline_lift=8.0)

def draw_test_box(atlas, glyphs, line_h, text, box_w, box_h, text_x, text_y, justify='left'):
    img = Image.new('RGBA', (box_w, box_h), (25, 20, 15, 255))
    draw = ImageDraw.Draw(img)
    # Highlight box border
    draw.rectangle([0, 0, box_w - 1, box_h - 1], outline=(220, 180, 80, 220), width=1)
    
    shaped = shape_thai_text(text)
    total_w = sum(glyphs[c].advance for c in shaped)
    
    if justify == 'center':
        pen_x = (box_w - total_w) / 2.0
    else:
        pen_x = float(text_x)
        
    baseline = float(text_y + line_h)
    
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
            img.alpha_composite(glyph_img, (dest_x, dest_y))
        pen_x += g.advance
    return img

test_cases = [
    ("1. Dialog Option (Font 6 Glow_VL)", "ขอบคุณที่ขุดฉันออกมาจากหลุมนั้น", 460, 52, 25, 15, 'left', False),
    ("2. Pip-Boy Quest Item (Font 6)", "กลับสู่รัง", 220, 52, 20, 15, 'left', False),
    ("3. Confirmation Button (Font 2 Monofonto_Large)", "ใช่", 180, 51, 0, 20, 'center', True),
    ("4. Quit Menu Button (Font 2 Monofonto_Large)", "ออกเกม", 180, 51, 0, 20, 'center', True),
    ("5. Pip-Boy Tabs (Font 2 Monofonto_Large)", "World Map", 180, 51, 0, 20, 'center', True),
]

final_canvas = Image.new('RGBA', (950, 480), (12, 10, 8, 255))
fd = ImageDraw.Draw(final_canvas)
fd.text((150, 15), "BEFORE (Current: Bottom-Hugging & Overflow)", fill=(255, 100, 100, 255))
fd.text((600, 15), "AFTER (Baseline Lift +8px: Centered & Clean)", fill=(100, 255, 100, 255))

y = 45
for label, text, bw, bh, tx, ty, just, is_mono in test_cases:
    if is_mono:
        b0 = draw_test_box(atlas_m0, glyphs_m0, lh_m0, text, bw, bh, tx, ty, just)
        b8 = draw_test_box(atlas_m8, glyphs_m8, lh_m8, text, bw, bh, tx, ty, just)
    else:
        b0 = draw_test_box(atlas0, glyphs0, lh0, text, bw, bh, tx, ty, just)
        b8 = draw_test_box(atlas8, glyphs8, lh8, text, bw, bh, tx, ty, just)
        
    fd.text((20, y - 10), label, fill=(200, 200, 150, 255))
    final_canvas.paste(b0, (20, y + 8))
    final_canvas.paste(b8, (480, y + 8))
    y += 82

out_path = r'C:\Users\saetanpee\.gemini\antigravity\brain\5220f6a4-fb4b-462e-bb76-2d8317f76742\hover_box_lift_comparison.png'
final_canvas.save(out_path)
print(f"Comparison image saved to: {out_path}")
