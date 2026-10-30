# DEVLOG — บันทึกการพัฒนา ThaiFNV

เติมรายการใหม่ไว้**บนสุด** ทุกครั้งที่จบงานที่มีผลต่อสถานะโปรเจกต์  
รูปแบบ: `## YYYY-MM-DD — หัวข้อสั้น` แล้ว bullet สิ่งที่เปลี่ยน / เรียนรู้ / ไฟล์ที่แตะ

---

## 2026-10-30 — เอกสารโปรเจกต์ + push GitHub

- เพิ่ม `CONTEXT.md`, `README.md`, `docs/STATUS.md`, `docs/DEVLOG.md`
- เขียน `pipeline_guide.md` ใหม่ให้ตรงกับสคริปต์จริง (ฉบับเก่าเสีย/ซ้ำ)
- อัปเดต `.gitignore` กั้นเครื่องมือภายนอกและโฟลเดอร์ขยะ
- สร้าง remote GitHub และ push branch `main`

## 2026-10-29 — pipeline_guide + MT Messages

- ซ่อม/สร้าง `pipeline_guide.md` (มีรอบที่ไฟล์เสียแล้ว rebuild)
- มี `FNV_Messages_translated.csv` จากการทดลอง MT
- วาง README สำหรับ `pipeline/xtranslator/` และ `pipeline/fnvedit/` (เครื่องมือโหลดเอง ไม่ commit)

## 2026-10-28 — ฟอนต์ใช้งานได้ + extract ครบหมวด

### ฟอนต์
- แก้บั๊ก UV สลับแกนใน `fnt_lib.py` — ข้อความหายทั้งเกม → กลับมาแสดง
- ยืนยันฟอร์แมต glyph 56 bytes (bearing / advance_extra / ascent) — ดู `2026-10-28-fnt-format-fix.md`
- Sarabun Bold + baked outline; เทียบขนาดกับ vanilla แล้วลดรอบหลายครั้ง
  - รอบล่าสุด: gameplay −26%, Pip-Boy −20%, เมนูตัวเลือก −20%
  - tracking ~8% ของขนาด; main menu ~8.9%; version info ~10.2%
  - กฎ justify: `bearing_x=0` (non-combining) + advance เป็นจำนวนเต็ม
- Batch build: vanilla 9 ไฟล์ + DarN 5 ไฟล์
- รายละเอียดขนาด/outline → `2026-10-28-bold-outline-and-size-calibration.md`

### ข้อความ
- `fnv_esm.py` v1.1: FULL/DESC + INFO/TERM/QUST → รวม ~67,656 แถว
- `make_categories.py` แยกชีต 9 หมวดใน `extracted/sheets/`
- Apps Script MT seed: `corpus/google_sheets/mt_seed.gs`
- Decision: แปล DIAL topic names; DarN เป็น patch แยก

### Phase 0
- Cleanup `FalloutPrefs.ini` ชี้ฟอนต์ไทยเก่าที่ไฟล์หายแล้ว → คืนค่า vanilla
- บันทึก → `2026-10-28-phase0-ini-cleanup.md`
- เพิ่ม `Rule.md` (ขอบเขตงาน agent)

## ก่อนหน้า (สรุป)

- สร้าง workspace นอกโฟลเดอร์เกม + git
- Prototype `fnt_lib` + font builder ชุดแรก
- วางโครง `plan.md` และโครงสร้างโฟลเดอร์
