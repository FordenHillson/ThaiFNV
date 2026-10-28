# แก้บั๊กฟอนต์: รูปแบบ .fnt ที่ถูกต้อง + ข้อความหายทั้งเกม (2026-10-28)

## อาการ
หลังติดตั้งฟอนต์ไทยที่สร้างจาก pipeline ข้อความทั้งเกม **ไม่แสดงเลย** — main menu,
HUD, pause menu ว่างหมด (เห็นแต่ texture ฉากกับ overlay) ทั้งที่ไฟล์ `.fnt`/`.tex`
มีขนาดถูกต้องและ atlas มีรูปตัวอักษรครบ

## สาเหตุจริง (root cause)
`pipeline/fnt_lib.py` เขียน/อ่าน quad ของ glyph **สลับแกน X กับ Y**:

```python
# เดิม (ผิด): f1=T, f2=L, f3=B, f4=L, f5=T, f6=R, f7=B, f8=R
```

เกมอ่าน 8 float แรกเป็น **4 มุม** ตามลำดับนี้:

```
f1,f2 = มุมบนซ้าย  (L, T)
f3,f4 = มุมบนขวา   (R, T)
f5,f6 = มุมล่างซ้าย (L, B)
f7,f8 = มุมล่างขวา  (R, B)
```

เมื่อสลับ L/T เกมจึงได้ rect ที่กลับด้าน (bottom < top) และกว้างผิด → quad ไปสุ่ม
พื้นที่ว่างใน atlas → ตัวอักษรโปร่งใสทั้งหมด

นอกจากนี้ยังเข้าใจผิดอีก 3 ช่อง:

| ช่อง | ที่เข้าใจเดิม | ความจริง |
|---|---|---|
| f11 | x offset | **bearing X** (ระยะ pen → ขอบซ้าย glyph) |
| f12 | y offset | **advance ส่วนเกิน**: `advance = width + f12` |
| f13 | advance | **ascent** (ขอบบน glyph → baseline); `quad top = baseline - ascent` |
| header float | 100000.0 | **line height** ของฟอนต์ (vanilla = 25–52) |

ผลที่ตามมา: ตัวอักษรถูกวางผิดแนวตั้ง (ใช้ advance เป็น ascent) และระยะเลื่อนผิด
(advance = 0 ทุกตัว) — แม้แก้ UV แล้วก็ยังอ่านไม่ได้

## หลักฐาน
1. **vanilla จริง** (`testing/vanilla_bsa_fonts/`, แตกจาก `Fallout - Textures2.bsa`
   ด้วย `pipeline/bsa_extract.py --filter fonts`):
   - `monofonto_large.fnt`: 'A' → `L=0.0547 T=0.5469 R=0.1133 B=0.6484`
     บน texture 256² → rect 14..29 × 140..166 = 15×26 px = `px_width/px_height` พอดี
   - `f12` คงที่ทุก glyph ของฟอนต์เดียว (space ใช้ f12 เป็นความกว้างช่องว่าง เช่น 7)
   - `f13` = ascent: 'A' h=26/f13=24, 'j' h=32/f13=24 (หาง j ยื่นล่าง baseline 8px),
     ',' h=12/f13=6 (อยู่เหนือ baseline 6px) — สอดคล้องกันทุก glyph
2. **OpenMW** (`components/fontloader/fontloader.cpp`) อ่าน .fnt ฟอร์แมตเดียวกัน
   และประกาศ struct ตรงกัน:
   ```c
   float mUnknown; Point mTopLeft, mTopRight, mBottomLeft, mBottomRight;
   float mWidth, mHeight, mKerningLeft, mKerningRight, mAscent;
   ```
   พร้อมสูตร `advance = mWidth + mKerningRight`,
   `glyph top = line_top + lineHeight - mAscent` (→ baseline = `line_top + lineHeight`)
3. **ทดสอบในเกมจริง**: หลังแก้ + ติดตั้ง `Sarabun_20` เข้า slot 1 ข้อความ HUD
   (`Oct/Sun`, `Rads: 0`, `EN: 0%`, `HP`, `AP`, `CND`, `24 ft.`) กลับมาแสดงครบ

## สิ่งที่แก้
- `pipeline/fnt_lib.py` — เขียนใหม่ทั้งไฟล์: 4 มุม UV ถูกต้อง, ฟิลด์
  `bearing_x` / `advance_extra` / `ascent`, `save_fnt(..., line_height=...)`,
  property `advance = px_width + advance_extra`
- `pipeline/font_builder.py` — สร้าง glyph จาก **ink box จริง** ของ TTF
  (วัดด้วยการวาดบน canvas เพราะ `font.getbbox()` ให้ความสูงเกินจริงกับ glyph
  ที่ advance = 0), ตั้ง `ascent`/`bearing`/`advance` จาก baseline,
  header = ascent+descent, shelf packing ต่อ glyph, atlas สี่เหลี่ยมจัตุรัส
- `pipeline/font_patch.py` — แพตช์บน vanilla: คง glyph เดิมทุกพิกเซล
  (ขยาย atlas เป็นสี่เหลี่ยมใหญ่ขึ้น + scale UV ของ glyph เดิม), เติมไทยในแถบว่าง,
  คง line height เดิม
- `pipeline/font_render.py` — จำลองการวาดแบบ engine (ตรวจผลก่อนเข้าเกม)
- `pipeline/font_check.py` — ตรวจ .fnt/.tex ก่อนติดตั้ง (UV กลับด้าน, ชื่อ header
  ไม่ตรงชื่อ .tex, สัดส่วน quad ไม่ตรง, ascent/advance ผิดปกติ)

## การวางสระ/วรรณยุกต์ไทย (เกมไม่ทำ shaping)
เกมวาดทีละ byte ไม่มี GPOS/GSUB จึงต้อง encode ตำแหน่งไว้ในตัว glyph เอง:

- สระบน/วรรณยุกต์/สระล่าง (`ั ิ ี ึ ื ุ ู ฺ ็ ่ ้ ๊ ๋ ์ ํ ๎`):
  - `advance = 0` → pen ไม่เลื่อน
  - `bearing_x = -(ความกว้างพยัญชนะอ้างอิง + ความกว้างมาร์ค) / 2` → เลื่อนไปกลางพยัญชนะตัวก่อน
  - `ascent` วัดจาก baseline ตามฟอนต์ → ความสูง (บน/ล่าง baseline) ถูกต้องเอง
- ตัวอักษรปกติ: `bearing_x` = left bearing ของ TTF, `advance` = `font.getlength()`

## ตรวจซ้ำ (reproduce)
```bat
cd pipeline
python font_builder.py --ttf ..\fonts\src\Sarabun-Regular.ttf --name Sarabun_20 --size 20 --out ..\fonts\out\Sarabun_20
python font_check.py ..\fonts\out\Sarabun_20.fnt
python font_render.py --fnt ..\fonts\out\Sarabun_20.fnt --text "CONTINUE\nสวัสดีครับ" --out ..\testing\check.png
```

## หมายเหตุ / งานต่อไป
- วรรณยุกต์วางที่ความสูงคงที่ (ตามที่ฟอนต์ออกแบบ) ไม่ปรับตามความสูงพยัญชนะแต่ละตัว
  เพราะเกมไม่มี state ของตัวก่อนหน้า — ถ้าต้องการละเอียดกว่านี้ต้องใช้ glyph ผสม
  (cluster) ซึ่ง byte ต่อ glyph ไม่พอ
- `font_patch.py` คง line height ของ vanilla ไว้ → วรรณยุกต์ไทยอาจล้นขึ้นบรรทัดบน
  ถ้า UI นั้นระยะบรรทัดแน่น (เหมือนแนวทางของ FNVThai) — ถ้าพบปัญหาค่อยเพิ่มออปชัน
  ขยาย line height
- ยังไม่ได้ทดสอบข้อความไทยจริงในเกม (HUD เป็นอังกฤษ) — ต้องรอ Phase 2 ตอนใส่
  ข้อความแปลลง record แรก
