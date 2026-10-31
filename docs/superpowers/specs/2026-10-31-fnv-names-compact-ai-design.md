# FNV_Names Compact AI Translation (CSV-only)

**Date:** 2026-10-31  
**Status:** draft for user review  
**Scope:** แปล `extracted/sheets/FNV_Names.csv` ให้ครบ แล้วให้คนอัปโหลด Google Sheet / ดึงกลับตาม workflow เดิม

## Goal

แปลคอลัมน์ `TH` ของ `FNV_Names.csv` ด้วย Cursor agent โดยประหยัด token สูงสุด และคุณภาพชื่อในเกมสูง โดย**ไม่**ใช้วิธีเดิมในโปรเจกต์ (`mt_seed_local.py`, Apps Script MT, แพตเทิร์น batch JSON ของ Notes)

ผลลัพธ์ที่ต้องการคือ CSV พร้อม `TH` + สถานะ สำหรับนำไปใส่ Google Sheet เท่านั้น — **ไม่อยู่ในขอบเขต:** push Sheets API, import ESP, แปลชีตอื่น

## Constraints (locked)

| ข้อ | ค่า |
|---|---|
| ผู้แปล | Cursor agent ในแชท |
| คุณภาพ | สูง — โทน Fallout / UI สั้นชัด |
| ชื่อเฉพาะ | คง EN (คน / องค์กร / สถานที่หลัก / ย่อหน้า) |
| TM จาก Messages | ไม่ใช้ — ใช้ glossary สั้นเท่านั้น |
| วิธีเก่า | ห้าม reuse เป็นหลัก |
| เป้าหมายไฟล์ | `extracted/sheets/FNV_Names.csv` เท่านั้น |

## Data facts

- ~13,177 แถว · `TH` ว่างทั้งหมดตอนเริ่มงาน
- ~5,750 สตริง `EN` ไม่ซ้ำ (เฉลี่ย ~14 ตัวอักษร)
- การ dedupe ตัดงาน agent เกือบครึ่งก่อนแปล

## Approach

**Compact Unique Pack + กรองอัตโนมัติ**

1. สร้าง glossary สั้น  
2. ดึง `EN` ไม่ซ้ำ → แยก `keep` / `need_ai`  
3. แพ็ก TSV กะทัดรัดให้ agent  
4. Agent แปลทีละแพ็กในแชท  
5. Merge กลับ CSV เดิม (resume ได้)  
6. คนอัปโหลด Sheet เอง

## Components

### 1. Glossary สั้น

- Path: `corpus/names_glossary_short.md`
- เนื้อหาสั้นมาก: รายการคง EN + คำทั่วไปที่ล็อกคำแปล (เช่น Trooper, Ranger, Door)
- กฎ: แปลคำทั่วไปรอบชื่อเฉพาะ · ทั้งสตริงเป็นชื่อเฉพาะล้วน → คง EN · ไม่ดึง Messages

### 2. Pack / merge script

- Path: `pipeline/names_compact_pack.py`
- คำสั่งหลัก (ชื่ออาจปรับตอน implement ให้สอดคล้อง argparse):
  - `build` — สร้าง index + แพ็ก `need_ai`
  - `merge` — อ่านผลแพ็ก + `keep` แล้วเขียน CSV
  - `status` — แสดงค้างกี่แพ็ก / เติม TH แล้วกี่แถว

### 3. Pack files

- `extracted/sheets/names_packs/en_index.json` — map `n → EN`, metadata resume
- `extracted/sheets/names_packs/in/u_XXXX.tsv` — อินพุต `n\tEN`
- `extracted/sheets/names_packs/out/u_XXXX.tsv` — เอาต์พุต `n\tTH`
- ขนาดแพ็ก: **80–100** บรรทัด
- **ไม่ใส่** FormID / EditorID / ประเภท ในแพ็ก

### 4. Auto filter buckets

| Bucket | เงื่อนไข | ผลใน CSV |
|---|---|---|
| `keep` | ทั้งสตริงเป็นชื่อเฉพาะตาม glossary / allowlist | `TH=EN`, `สถานะ=keep`, หมายเหตุเช่น `proper-noun` |
| `need_ai` | ที่เหลือ | รอแพ็ก → หลังแปล `สถานะ=ai` |
| editorid-like | camelCase ไม่มีช่องว่าง | ค่าเริ่มต้น: `keep` + หมายเหตุ `editorid-like` (ลด noise ใน UI ชื่อ) |

ไม่ใช้สถานะ `mt` เพื่อไม่ปนกับ pipeline MT เดิม

### 5. Agent turn contract

แต่ละรอบแปล:

1. อ่าน `corpus/names_glossary_short.md` (ถ้ายังไม่อยู่ในบริบท)
2. อ่านแพ็ก `in/u_XXXX.tsv` หนึ่งไฟล์
3. เขียน `out/u_XXXX.tsv` เป็น `n\tTH` เท่านั้น จำนวนบรรทัดเท่าอินพุต
4. สุ่ม QA สั้น 5–10 บรรทัดในแชทเมื่อมีข้อสงสัย; ไม่เขียนเรียงความยาว

ห้ามใส่คอลัมน์เกิน · ห้ามเว้น `n` · ห้ามแปลชื่อเฉพาะที่กฎให้คง EN

### 6. Merge rules

- สร้าง map `EN → TH` จากทุกไฟล์ใน `out/` + รายการ `keep`
- กระจายไปทุกแถวที่ `EN` ตรงกัน
- ไม่ทับแถวที่มี `TH` อยู่แล้ว หรือ `สถานะ` เป็น `ok` / `fix`
- เขียน atomic (temp + replace) · รันซ้ำต่อจากแพ็กที่ยังไม่มี `out/`

## Data flow

```text
FNV_Names.csv
    → build unique EN + filter
    → in/u_XXXX.tsv (+ keep list)
    → Cursor agent (glossary + one pack)
    → out/u_XXXX.tsv
    → merge
    → FNV_Names.csv (TH filled)
    → (human) Google Sheet upload / pull แบบเดิม
```

## Error handling

- แพ็ก out ไม่ครบ / `n` หายหรือซ้ำ → `merge` ปฏิเสธแพ็กนั้น พร้อมรายการผิด
- `TH` ว่างใน out → ปฏิเสธแพ็ก
- แท็บเกินในบรรทัด → ปฏิเสธหรือ escape ตามที่ implement เลือกแบบ fail-fast
- ไฟล์ CSV ต้นทางหาย → หยุดทันที

## Testing / verification

- นับ unique EN ก่อน/หลัง build ตรงกัน
- ทุกแพ็ก `in` มีบรรทัด 80–100 (แพ็กท้ายอาจน้อยกว่า)
- หลัง merge: จำนวนแถว CSV ไม่เปลี่ยน · คอลัมน์เดิมครบ
- สุ่มตรวจ: ชื่อเฉพาะคง EN · คำทั่วไปเป็นไทย · ไม่มี FormID หลุดใน TH
- `status` รายงาน % แถวที่มี TH

## Out of scope

- Google Sheets API push/pull ในรอบนี้
- `esp_apply_thai` / import Names เข้า ESM
- แปล `FNV_Dialogue` / Notes / Quests
- การใช้ Google/MyMemory/`mt_seed_local` เป็น engine หลัก

## Success criteria

1. `FNV_Names.csv` ทุกแถวมี `TH` ไม่ว่าง และ `สถานะ` เป็น `ai` หรือ `keep`
2. ไม่พึ่ง MT engine เดิม
3. Payload ที่ส่งเข้า agent เป็น unique EN แบบ TSV สั้น ไม่ใช่ทั้งชีต
4. ไฟล์พร้อมให้คนอัปโหลด Sheet ตาม workflow เดิม
