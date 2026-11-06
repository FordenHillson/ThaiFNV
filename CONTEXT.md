# ThaiFNV — Context สำหรับการพัฒนา

Mod แปลภาษาไทยสำหรับ **Fallout: New Vegas**  
workspace: `D:\backup\github\ThaiFNV`

---

## สถานะปัจจุบัน

- **ระบบ Data Extraction**: ✅ พัฒนา Extractor ใหม่เสร็จสมบูรณ์ และสกัดข้อความเกมตัวเต็ม + DLC 9 ตัว ทั้งหมด 90,074 แถว พร้อมระบุ DLC, หมวดหมู่ และชื่อตัวละครผู้พูด (Speaker) ในบทสนทนา
- **ระบบ Font**: รอออกแบบและสร้างระบบ Render/Atlas ใหม่
- **ระบบแปล & Corpus**: คงข้อมูลชุดแปลเดิมและคลังศัพท์ไว้ทั้งหมดใน `corpus/`

---

## โครงสร้างโฟลเดอร์ปัจจุบัน

```
ThaiFNV/
├── CONTEXT.md          ← ภาพรวมโปรเจกต์
├── README.md           ← ข้อมูลสรุปโปรเจกต์
├── plan.md             ← แผนการทำงาน
├── docs/               ← บันทึกความคืบหน้า (STATUS, DEVLOG)
├── corpus/             ← คลังศัพท์, Backup ชีต, Google Apps Script
├── extracted/
│   ├── README.md           ← สรุปสถิติและ Manifest การแกะข้อความ
│   ├── extraction_summary.json
│   ├── by_category/        ← ไฟล์ข้อความรวมแยกตาม 13 หมวดหมู่
│   ├── by_dlc/             ← ไฟล์ข้อความแยกเป็นโฟลเดอร์ตามแต่ละ DLC
│   └── sheets/             ← สำหรับใช้ซิงค์กับ Google Sheets / Pipeline
└── pipeline/
    └── extract_fnv_full.py ← สคริปต์สกัดข้อความความเร็วสูง (Base + All DLCs)
```

---

## สรุปฐานข้อมูลข้อความที่สกัดได้ (90,074 แถว)

1. `FNV_Dialogue.csv` (39,115 แถว) — บทสนทนาพร้อมชื่อตัวละครผู้พูด (Speaker), อารมณ์ (Emotion), บันทึกกำกับเสียง (ActorNotes)
2. `FNV_TopicNames.csv` (21,521 แถว) — หัวข้อบทพูดในเมนูเลือก
3. `FNV_World_Objects.csv` (11,871 แถว) — ชื่อ NPC, มอนสเตอร์, ฝ่าย, สถานที่, ประตู, กล่อง
4. `FNV_Terminals.csv` (3,357 แถว) — ข้อความหน้าจอเทอร์มินัล
5. `FNV_Items.csv` (3,120 แถว) — อาวุธ, ชุดเกราะ, ยา, ขยะ, กุญแจ, การ์ด
6. `FNV_Messages.csv` (2,950 แถว) — กล่องข้อความแจ้งเตือน, ปุ่มกดยืนยัน
7. `FNV_Notes.csv` (2,226 แถว) — จดหมาย, ข้อความบันทึก, เทปเสียง
8. `FNV_Quests.csv` (1,974 แถว) — ชื่อเควส และเป้าหมายเควส
9. `FNV_Perks_Skills.csv` (1,973 แถว) — Perks, Traits, SPECIAL, Spells, Challenges
10. `FNV_Other.csv` (1,509 แถว) — คลาส, เผ่าพันธุ์, ข้อความอื่น ๆ
11. `FNV_LoadScreens.csv` (283 แถว) — ข้อความ Lore หน้าโหลดเกม
12. `FNV_GameSettings.csv` (129 แถว) — ข้อความระบบ UI ฮาร์ดโค้ด (Yes, No, Take All...)
13. `FNV_Books.csv` (46 แถว) — หนังสือ และนิตยสารสกิล
