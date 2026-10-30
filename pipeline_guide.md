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

ชีต: https://docs.google.com/spreadsheets/d/1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE

1. วาง Apps Script จาก `corpus/google_sheets/mt_seed.gs` (Extensions → Apps Script)
2. เมนู **🇹🇭 ThaiFNV → Import หมวดที่เหลือจาก GitHub**  
   (ดึง CSV จาก `extracted/sheets/` บน GitHub เข้าแท็บใหม่ — ข้ามแท็บที่มีแล้ว)
3. รัน **MT Seed** เติมคอลัมน์ `TH` + ตั้ง `สถานะ = mt`
4. คนแก้ต่อ → `สถานะ = ok` / `fix`
5. ดึงกลับ:

```bash
python pipeline/sheets_sync.py list
python pipeline/sheets_sync.py pull
```

CSV ไปที่ `extracted/sheets/from_google/` + backup ใน `corpus/sheets_backup/`

ดูไฟล์ที่รออัปโหลด: `python pipeline/sheets_sync.py pending`

---

## 4) ป้อนกลับเข้าเกม (MESG)

```bash
# ดาวน์โหลดชีต (gid ของแท็บ FNV_Messages)
curl -L -o extracted/sheets/from_google/FNV_Messages.csv \
  "https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=<GID>"

python pipeline/import_csv_to_esp.py extracted/sheets/from_google/FNV_Messages.csv \
  --esm "D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\FalloutNV.esm" \
  --out release/ThaiFNV_Messages.esp
```

คัดลอก ESP ไป `Data\` แล้วเปิดใน load order (หลัง master)  
รายละเอียด → `docs/2026-10-30-import-messages.md`

หมวดอื่น / xTranslator → ยังใช้คู่มือใน `pipeline/xtranslator/README.md` ได้

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
