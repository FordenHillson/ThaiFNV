# สถานะโปรเจกต์ ThaiFNV

**อัปเดตล่าสุด:** 2026-10-30

> ไฟล์นี้คือ snapshot สั้น ๆ — เปลี่ยนเมื่อจบงานใหญ่แล้ว  
> รายละเอียด timeline → [DEVLOG.md](DEVLOG.md) · แผนเต็ม → [../plan.md](../plan.md)

## เฟส

| เฟส | ชื่อ | สถานะ |
|---|---|---|
| 0 | เตรียม workspace + แก้ INI พัง | ✅ เสร็จ |
| 1 | Extract ข้อความ → Sheets | 🟡 extract เสร็จ / MT + glossary กำลังทำ |
| 2 | Prototype ฟอนต์ในเกม | ✅ ผ่าน (ปรับขนาดหลายรอบ) |
| 3 | MT seed + human post-edit | ⬜ เริ่มแล้วบางส่วน (Messages) |
| 4 | ป้อนแปลกลับ ESM | ⬜ ยังไม่ทำ |
| 5 | FOMOD / แพ็กเกจ | ⬜ ยังไม่ทำ |
| 6 | DLC / YUP / major mods | ⬜ |
| 7 | เผยแพร่ | ⬜ |

## Build ล่าสุดที่ใช้งานได้

- ฟอนต์: `fonts/out/vanilla/` + `fonts/out/darn/` (Sarabun Bold, sizes 21/20/18/20/24/21/21/42/31)
- Extract: `extracted/sheets/*.csv` จาก FalloutNV.esm
- ทดลองแปล: `extracted/sheets/FNV_Messages_translated.csv`

## บล็อกเกอร์ / คำถามเปิด

- Round-trip CSV → ESM ด้วย CP874 ยังไม่พิสูจน์ครบ pipeline
- Glossary มาตรฐานยังไม่ล็อกทั้งชุด
- ลิขสิทธิ์การแจก `.esm` แก้แล้ว — แผนระยะยาวอาจเป็น translation plugin

## Next 3 อย่าง

1. ขยาย MT seed + Glossary บน Google Sheets
2. Post-edit หมวด Messages / Names
3. สคริปต์ import กลับ + ทดสอบในเกม
