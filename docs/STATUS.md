# สถานะโปรเจกต์ ThaiFNV

**อัปเดตล่าสุด:** 2026-11-05

---

## สถานะปัจจุบัน

- **Font System**: รอออกแบบและพัฒนาใหม่ (Clean Slate)
- **Data Extraction**: ✅ **เสร็จสมบูรณ์ 100% (Base Game + 9 DLCs)**
  - พัฒนา Extractor ตัวใหม่ความเร็วสูง: [`extract_fnv_full.py`](file:///d:/backup/github/ThaiFNV/pipeline/extract_fnv_full.py)
  - สกัดข้อความครบทั้งหมด **90,074 แถว** (Base Game, Dead Money, Honest Hearts, Old World Blues, Lonesome Road, Gun Runners' Arsenal, Courier's Stash)
  - จัดหมวดหมู่ 13 หมวดใน `extracted/by_category/` และ `extracted/sheets/`
  - จัดชุดแยกโฟลเดอร์ตาม DLC ใน `extracted/by_dlc/`
  - บทสนทนา (`FNV_Dialogue.csv`): ระบุชื่อผู้พูด (`Speaker`) ได้สำเร็จถึง **91.0%** (35,604 / 39,115 บรรทัด) พร้อมอารมณ์ (`Emotion`) และโน้ตกำกับเสียง (`ActorNotes`)
  - คอลัมน์ภาษาไทย (`TH`) เว้นว่างไว้พร้อมสำหรับเริ่มงานแปล
- **Translation Data**: เก็บรักษาคลังศัพท์ใน `corpus/` ไว้อย่างปลอดภัย
