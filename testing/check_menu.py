import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'd:\backup\github\ThaiFNV\pipeline')

import sys
from PIL import Image

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'd:\backup\github\ThaiFNV\pipeline')

from PIL import Image, ImageDraw
from fnt_lib import load_fnt
from thai_shaper_engine import shape_thai_text
import struct

fnt_path = r'D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\Textures\Fonts\Glow_Monofonto_VL_dialogs.fnt'
png_path = r'D:\backup\github\ThaiFNV\fonts\out\vanilla\Glow_Monofonto_VL_dialogs.png'

tex_name, glyphs = load_fnt(fnt_path)
with open(fnt_path, 'rb') as f:
    line_h = struct.unpack('<f', f.read(4))[0]

atlas = Image.open(png_path)

# Let's render the dialog box with S=0 (current) vs S=5 (lifted)
def render_box(baseline_lift, title):
    box_w, box_h = 500, int(line_h + 20)  # 52px
    img = Image.new('RGBA', (box_w, box_h), (25, 20, 15, 255))
    draw = ImageDraw.Draw(img)
    # Yellow border
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
            dest_y = int(round(baseline - (g.ascent + baseline_lift)))
            img.alpha_composite(glyph_img, (dest_x, dest_y))
        pen_x += g.advance
        
    return img

img_current = render_box(0.0, "Current (S=0)")
img_lifted = render_box(5.0, "Lifted (S=5)")

combined = Image.new('RGBA', (520, 150), (10, 10, 10, 255))
draw = ImageDraw.Draw(combined)
combined.paste(img_current, (10, 15))
combined.paste(img_lifted, (10, 80))
combined.save(r'C:\Users\saetanpee\.gemini\antigravity\brain\5220f6a4-fb4b-462e-bb76-2d8317f76742\simulated_lift_comparison.png')
print("Comparison saved successfully!")





w, h = img.size
# Pip-Boy quest box











