# Thai precompose (ชั้น 3) — 2026-10-30

## ปัญหา
เกมไม่มี OpenType shaping: ลำดับ `ี`+`่` ถูกวางเป็น 2 glyph ข้างกัน  
(แบบ FNVThai: `bear=-w`, `adv=w`) → คำว่า `ที่` / `ชิ้น` / `เปลี่ยน` ดูซ้อน/บีบ

การตั้ง `advance=0` ทั้งชุด combining ทำให้ spacing แนวนอนพัง

## วิธีแก้
รวม **สระบน + วรรณยุกต์** เป็น 1 combining glyph ในช่อง CP874 ว่าง:

| ช่วง | ใช้ทำ |
|------|--------|
| `0x80`–`0x9B` (28 ช่อง) | `ั่ ั้ … ี่ ี้ … ํ๋` (7 สระบน × 4 วรรณยุกต์) |

ไฟล์:
- `pipeline/thai_precompose.py` — ตาราง map + `compose_cp874` / `expand_cp874`
- `pipeline/font_builder.py` — วาด glyph ซ้อนแนวตั้งลงช่องเหล่านี้

## การใช้กับข้อความแปล
หลัง encode CP874 ปกติ ให้รัน compose:

```python
from thai_precompose import compose_cp874, encode_thai_cp874
data = encode_thai_cp874("หุ่นยนต์ที่เสียหาย")  # มี precompose ในตัว
# หรือ
data = compose_cp874(text.encode("cp874"))
```

ต้อง **compose ตอนเขียน ESP** — ฟอนต์อย่างเดียวไม่พอ  
เพราะเกมยังส่ง `ี`+`่` แยก byte ถ้าข้อความไม่ถูกแทนที่

### แพตช์ ESP ที่มีอยู่แล้ว
```text
python pipeline/compose_esp_text.py path\ThaiFNV_Test.esp --in-place
python pipeline/compose_esp_text.py path\FalloutNV_Thai.esp --out path\FalloutNV_Thai_pre.esp
```
- เดิน GRUP/record จริง แก้ FULL/DESC/ITXT/NNAM/TNAM/NAM1/RNAM
- สั้นลงแล้ว pad `0x00` ให้ยาวเท่าเดิม (ไม่เลื่อนขนาด record)
- `--in-place` สร้าง `.precompose.bak` ครั้งแรก
- ไม่แตะ record ที่ compress / ไม่แตะ DATA (GMST)

ตัวอย่าง map: `ที่` → `b7 88` · `ชิ้น` → `aa 85 b9` · `เปลี่ยน` → `… 88 …`

## สถานะ
- [x] ตาราง 28 ชุด + ช่องว่างเพียงพอ
- [x] สร้าง glyph ในฟอนต์ (vanilla ทั้งชุด, 209 glyphs)
- [x] แก้พิกัดวาด precompose (ซ้อนสระ+วรรณยุกต์ในช่อง — เคย offset ผิดจนหมึกเกือบหาย)
- [x] `compose_esp_text.py` + รันบน `ThaiFNV_Test.esp` (6 สตริง, มี `.precompose.bak`)
- [x] staging `fonts/out/esp_precompose/*_Thai.esp` (FalloutNV ~20k สตริง)
- [x] ทดสอบในเกมกับ `ที่` / `ชิ้น` / `เปลี่ยน` — โอเคแล้ว
- [x] ตัดคำ: `thai_wordbreak.py` (sparse) + `esp_apply_thai.py` บน `ThaiFNV_Test.esp`
- [ ] ผู้ใช้ตรวจตัดบรรทัดในเกม (ไม่ควรมี `เป-` / `ลี่ยน`)
