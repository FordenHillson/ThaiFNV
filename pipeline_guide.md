# Pipeline Guide — ThaiFNV

คู่มือรันสคริปต์จริงใน `pipeline/`  
อัปเดตเมื่อเพิ่ม/เปลี่ยนคำสั่งหรือ path

---

## ข้อกำหนด

- Python 3.10+ (`Pillow` สำหรับฟอนต์; stdlib พอสำหรับ extract)
- ฟอนต์ต้นทาง: `fonts/src/Sarabun-Bold.ttf`
- เครื่องมือภายนอก (โหลดเองตาม README ในโฟลเดอร์):
  - `pipeline/xtranslator/` — export/import ข้อความระดับเครื่องมือ GUI
  - `pipeline/fnvedit/` — ตรวจ record / conflict

รันจากรากโปรเจกต์ หรือ `cd pipeline` แล้วเรียกสคริปต์ในโฟลเดอร์นั้น

```bash
cd D:\backup\github\ThaiFNV
pip install Pillow
```

---

## 1) ฟอนต์ (.fnt / .tex)

### Build ชุดเต็ม

```bash
python pipeline/font_builder.py --ttf fonts/src/Sarabun-Bold.ttf --batch vanilla --out-dir fonts/out/vanilla
python pipeline/font_builder.py --ttf fonts/src/Sarabun-Bold.ttf --batch darn --out-dir fonts/out/darn
```

ชุด `FONTSETS` อยู่ในท้าย `font_builder.py` (ชื่อไฟล์ + ขนาด px + line height + tracking)

### ไฟล์เดี่ยว

```bash
python pipeline/font_builder.py --ttf fonts/src/Sarabun-Bold.ttf --name Glow_Monofonto_Large --size 21 --out fonts/out/vanilla --outline 2 --outline-color 6A5C40
```

### ตรวจก่อนติดตั้ง

```bash
python pipeline/font_check.py fonts/out/vanilla/Glow_Monofonto_Large.fnt
```

### จำลองการวาด (ไม่เปิดเกม)

```bash
python pipeline/font_render.py fonts/out/vanilla/Glow_Monofonto_Large.fnt --text "ทดสอบภาษาไทย" --out testing/sim.png
```

### แตกฟอนต์ vanilla จาก BSA (อ้างอิง)

```bash
python pipeline/bsa_extract.py --filter fonts "D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\Fallout - Textures2.bsa" --out testing/vanilla_bsa_fonts
```

ผลลัพธ์ `testing/vanilla_bsa_fonts/` ถูก gitignore (ลิขสิทธิ์ Bethesda)

### ติดตั้งลงเกม (ทดสอบ)

คัดลอก `.fnt` + `.tex` จาก `fonts/out/vanilla/` ไปที่  
`Data\Textures\Fonts\` (ผ่าน MO2/Vortex overlay หรือคัดลอกตรง — ตามที่ผู้ใช้สั่งเท่านั้น)

---

## 2) Extract ข้อความจาก ESM

```bash
python pipeline/fnv_esm.py ^
  "D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\FalloutNV.esm" ^
  --out extracted/FalloutNV_extract_v1.csv
```

ดึง: FULL ทุกชนิด + DESC/ITXT ตามประเภท + INFO NAM1 + TERM + QUST NNAM  
ดูตารางใน docstring ของ `fnv_esm.py`

### แยกหมวดสำหรับ Google Sheets

```bash
python pipeline/make_categories.py extracted/FalloutNV_extract_v1.csv --out-dir extracted/sheets
```

ได้ไฟล์เช่น `FNV_Dialogue.csv`, `FNV_Names.csv`, …  
คอลัมน์: `ID | ประเภท | FormID | EditorID | EN | TH | สถานะ | หมายเหตุ`

### ดูชนิด subrecord (debug)

```bash
python pipeline/inspect_subs.py "path\to\FalloutNV.esm"
```

---

## 3) Machine Translation seed (Google Sheets)

1. อัปโหลด CSV จาก `extracted/sheets/` ขึ้นชีต (หนึ่ง tab ต่อหมวด)
2. วาง Apps Script จาก `corpus/google_sheets/mt_seed.gs`
3. รัน MT เติมคอลัมน์ `TH` + ตั้ง `สถานะ = mt`
4. คนแก้ต่อ → `สถานะ = edited` / `final`
5. ดาวน์โหลด CSV เก็บ backup ลง `corpus/` เมื่อจบรอบใหญ่

ทดลองแปล Messages: `extracted/sheets/FNV_Messages_translated.csv`

---

## 4) ป้อนกลับเข้าเกม (ยังไม่สมบูรณ์ใน pipeline)

เป้าหมายระยะถัดไป:

1. CSV แปลแล้ว → XML / หรือเขียนตรงเข้า ESM ด้วยเครื่องมือ (xTranslator Esp mode หรือสคริปต์)
2. encoding ข้อความไทย = **CP874** ให้ตรงตาราง glyph
3. Round-trip: EN → TH → เปิดเกมตรวจจุดสำคัญ

จนกว่าจะมีสคริปต์ import ใช้ **xTranslator** ตามคู่มือใน `pipeline/xtranslator/README.md`

---

## 5) จับภาพทดสอบในเกม

สคริปต์ใน `testing/capture_*.py` — รันเมื่อผู้ใช้สั่งตรวจเท่านั้น (ตาม `Rule.md`)

ภาพ `testing/*.png` ไม่เข้า git

---

## Checklist หลังเปลี่ยนฟอนต์

1. `font_builder` batch ที่เกี่ยวข้อง
2. `font_check` ไฟล์หลักอย่างน้อย 1–2 สล็อต
3. ติดตั้งลง Data (ตามที่ผู้ใช้ขอ)
4. ผู้ใช้เปิดเกมตรวจ → รอ "ok" / "แก้ไข"
5. บันทึกผลใน `docs/DEVLOG.md` + อัปเดตขนาดใน `CONTEXT.md` ถ้าเปลี่ยน

## Checklist หลัง extract / แปลรอบใหญ่

1. นับแถวต่อหมวด เทียบรอบก่อน
2. Backup CSV ลง `corpus/` พร้อมวันที่
3. อัปเดตตารางตัวเลขใน `CONTEXT.md` และ `docs/STATUS.md`
4. เติม `docs/DEVLOG.md`
