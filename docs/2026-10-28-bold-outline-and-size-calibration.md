# ฟอนต์หนา + เส้นขอบ + ปรับขนาดตาม vanilla (2026-10-28)

## โจทย์
ฟอนต์ไทยชุดแรกดู "เรียบเกินไป" เมื่อเทียบกับฟอนต์เกมเดิม → ต้องการ
**Sarabun Bold (700)** และ **เส้นขอบรอบตัวอักษร** ให้ดูเป็นสติกเกอร์แบบ reference

## 1) เปลี่ยนน้ำหนักฟอนต์เป็น Sarabun Bold
- ใช้ `fonts/src/Sarabun-Bold.ttf` (น้ำหนัก 700) แทน `Sarabun-Regular.ttf`
- ไม่ต้องแก้โค้ด — `--ttf` รับไฟล์ใดก็ได้ แต่ค่า default ในเอกสาร/คำสั่งเปลี่ยนเป็น Bold

## 2) เส้นขอบ (outline) — ต้องอบใน texture
เกม **ไม่มี** text outline ให้ใช้ (ไม่มีทั้ง XML attribute และ shader) จึงต้อง
วาดเส้นขอบลงใน atlas โดยตรง

### หลักการสำคัญ: เกมคูณสี
engine วาด glyph ด้วย `vertex color (จาก XML / SetTextColor) × RGB ใน texture`
ถ้าใส่สีขอบเข้มไว้ตรง ๆ สีจะถูกคูณซ้ำ → กลายเป็นดำ

```
สีที่เห็น = สีใน atlas × tint ของเกม
ตัวอย่าง:  #6A5C40 × #E0B93C ≈ (93, 68, 14)   ← น้ำตาลมะกอกเข้ม กำลังดี
          #2E2410 × #E0B93C ≈ (41, 26, 2)     ← ดำเกิน อ่านไม่ออก
```

จึงเลือกสีขอบเป็น **โทนกลาง-อบอุ่น** ไม่ใช่ดำ:

| ค่า | สี | บทบาท |
|---|---|---|
| `DEFAULT_OUTLINE_COLOR` | `#6A5C40` | วงนอก (เข้ม) |
| `DEFAULT_OUTLINE_INNER` | `#B0A078` | วงใน (อ่อนกว่า) → ได้ bevel แบบสติกเกอร์ |

ตัวอักษรยังเป็น **สีขาวล้วน** ใน atlas เพื่อให้ tint ของเกมคุมสีจริงได้
(ถ้าอบสีทองไว้ เกมจะคูณจนเพี้ยน)

### ลำดับการวาด (`draw_glyph`)
1. วงนอก: `stroke_width = outline`, `stroke_fill = #6A5C40`
2. วงใน: `stroke_width = outline // 2`, `stroke_fill = #B0A078`
3. ตัวอักษร: ขาวทึบ

### ความหนา (`auto_outline`)
```python
1 if size < 20 else 2
```
- ตัวเล็ก (10–19px) ใช้ 1px ไม่งั้นตัวติดกันเป็นพืด
- 20px ขึ้นไปใช้ 2px ให้ได้ลุคหนาแบบ reference
- 3px ขึ้นไปทดสอบแล้วตัวอักษรทับกันหนัก อ่านยาก

### ห้ามขยาย advance
ทดสอบ `advance += 2 * outline` เพื่อเว้นที่ให้เส้นขอบ → **ข้อความถูก clip**
("Downloadable Content" ใน main menu ถูกตัดที่ขอบกล่อง) เพราะเมนูเกมกำหนด
ความกว้างกรอบตายตัว

**สรุป: `advance = font.getlength(ch)` เท่านั้น** ยอมให้เส้นขอบของตัวที่ติดกัน
เหลื่อมกันเล็กน้อย (ที่ 31px ยังแยกตัวได้สบาย)

### ระยะขอบ atlas
`pad = max(1, outline + 1)` — กัน bleed ตอน sampling และกันเส้นขอบถูกตัดที่ขอบ rect

## 3) ปรับขนาดฟอนต์ตาม vanilla (ของเดิมเดาผิด)
ขนาดเดิม (20/20/18/26/16/22/20/24/16) เป็นการเดาจากชื่อไฟล์ ทำให้ตัวอักษร
**เล็กกว่าของเดิมราวครึ่งหนึ่ง** → ข้อความดูบางและกินพื้นที่น้อยเกินไป

### วิธีวัด
วัดจาก vanilla จริงใน `testing/vanilla_bsa_fonts/` (แตกจาก BSA) 2 ค่า:
- `advance` เฉลี่ยของ a–z
- ความสูงหมึกของ `H` (threshold alpha > 128 แล้ววัด bounding box)

แล้วเลือกขนาด Sarabun Bold ที่ให้ค่าทั้งสองใกล้เคียงที่สุด (ถ่วงน้ำหนักทั้งคู่)

| ไฟล์ | ขนาดใหม่ | line height (vanilla) |
|---|---|---|
| `Glow_Monofonto_Large` | 31 | 31 |
| `Monofonto_Large` | 29 | 31 |
| `Glow_Monofonto_Medium` | 26 | 26 |
| `Monofonto_VeryLarge02_Dialogs2` | 40 | 36 |
| `Fixedsys_Comp_uniform_width` | 28 | 25 |
| `Glow_Monofonto_VL_dialogs` | 34 | 34 |
| `Baked-in_Monofonto_Large` | 31 | 36 |
| `Glow_Futura_Caps_Large` | 50 | 52 |
| `NVFont_Test` | 37 | 36 |

`line_height` ใช้ค่าของ vanilla ตรง ๆ (ไม่ใช่ ascent+descent ของ TTF) เพื่อไม่ให้
กล่องข้อความเดิมล้น — วรรณยุกต์ไทยที่ล้นขึ้นบนเล็กน้อยยอมรับได้

## 4) เลิกใช้ชื่อไฟล์กำหนดเอง
เดิม slot 1 ชี้ไปที่ `Sarabun_20.fnt` (ชื่อใหม่) ทำให้ต้องแก้ INI และเสี่ยง
หลุดเมื่อผู้ใช้ลง mod อื่น

ตอนนี้แพ็กเป็น **drop-in replacement ของไฟล์ vanilla ทั้ง 9 ชื่อ**:
```
sFontFile_1 = Textures\Fonts\Glow_Monofonto_Large.fnt
...
sFontFile_9 = Textures\Fonts\NVFont_Test.fnt
```
ไม่ต้องแก้ INI เลย (ของผู้ใช้เดิมที่ชี้ `Sarabun_20` ให้เปลี่ยนกลับเป็นชื่อ vanilla)
→ ลบ `fonts/out/Sarabun_20.*` ออกแล้ว

## 5) เครื่องมือที่เพิ่ม
- `font_builder.py`
  - `--outline N` (px; ค่าเริ่มต้น = `auto_outline(size)`)
  - `--outline-color HEX` (วงนอก), `--outline-inner HEX|none` (วงใน)
  - `--line-height F` (บังคับความสูงบรรทัด)
  - `FONTSETS` เก็บ `(ชื่อไฟล์, ขนาด, vanilla line height)`
  - `draw_glyph()` แยกออกมาให้ปรับสไตล์เส้นขอบได้ที่เดียว
- `font_render.py`
  - `--color HEX` จำลอง tint ของเกม (คูณ RGB ใน texture)
  - `--bg HEX` ตั้งสีพื้นหลังเพื่อดูคอนทราสต์จริง

## 6) ตรวจในเกมจริง
- ติดตั้ง 15 ไฟล์ (vanilla 9 + DarN 5 + ชุดทดสอบ) ลง
  `Data\Textures\Fonts\` แล้วรันผ่าน `nvse_loader.exe`
- **main menu** (สล็อต 1) — "Continue / New / Load / Settings / Credits /
  Downloadable Content / Quit" แสดงครบ ไม่ถูกตัดขอบ ตัวหนา มีเส้นขอบ
- **บล็อกข้อมูลมุมซ้าย** (สล็อต 7 = `Baked-in_Monofonto_Large`) —
  "Fallout New Vegas 1.4.0.525", "Powered by xNVSE Version 6.49 b9" อ่านครบ
- ยืนยันสล็อตด้วย probe ไล่สีเส้นขอบทีละไฟล์ (แดง/เขียว/น้ำเงิน/…) แล้วถ่ายภาพ
  เทียบ: main menu = สล็อต 1, บล็อกข้อมูล = สล็อต 7
  (แม้ `start_menu.xml` จะระบุ `<font>4</font>` — จอจริงใช้สล็อต 7)

## 7) ข้อจำกัดที่รู้
- Sarabun มีสัดส่วน ink/advance ≈ 0.89 → เส้นขอบ > 2px ที่ 31px จะทำให้ตัวติดกัน
  และขยาย advance ไม่ได้ (เมนู clip) จึง **2px คือเพดานจริง** ที่ขนาดนี้
- ยังไม่ได้ทดสอบข้อความไทยในเกม (รอ Phase 2 ที่มี string แปลจริง)
  — ตรวจด้วย `font_render.py` แล้ว: สระบน/ล่าง/วรรณยุกต์วางถูกตำแหน่ง

## ตรวจซ้ำ
```bat
cd pipeline
python font_builder.py --ttf ..\fonts\src\Sarabun-Bold.ttf --batch vanilla --out-dir ..\fonts\out\vanilla
python font_builder.py --ttf ..\fonts\src\Sarabun-Bold.ttf --batch darn --out-dir ..\fonts\out\darn
python font_check.py ..\fonts\out\vanilla\Glow_Monofonto_Large.fnt
python font_render.py --fnt ..\fonts\out\vanilla\Glow_Monofonto_Large.fnt ^
  --text "Continue\nการตั้งค่า" --color E0B93C --bg 1A140C --out ..\testing\check.png
```
