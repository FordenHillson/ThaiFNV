# ThaiFNV — Context สำหรับการพัฒนา

Mod แปลภาษาไทยสำหรับ **Fallout: New Vegas**  
workspace: `D:\backup\github\ThaiFNV`

---

## สถานะปัจจุบัน

- **ระบบ Font & Extraction**: ได้ทำการลบรื้อระบบเดิมออกทั้งหมดเพื่อเตรียมออกแบบและพัฒนาใหม่ตั้งแต่ศูนย์
- **ระบบแปล & Corpus**: คงข้อมูลชุดแปลเดิมไว้ทั้งหมดใน `corpus/` และ `extracted/sheets/`
- **ประวัติเดิม**: โค้ดและบันทึกระบบเดิมทั้งหมดถูกสำรองไว้บน Git branch: `archive/legacy-font-and-extract`

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
│   └── sheets/         ← ไฟล์ข้อมูลข้อความและสถานะการแปล
└── pipeline/           ← สคริปต์ซิงค์ข้อมูลแปล / MT bridge
```

---

## ฐานข้อมูลการแปลที่เก็บไว้ (FalloutNV.esm)

- `Dialogue` (INFO NAM1)
- `TopicNames` (DIAL FULL)
- `Names`
- `Messages`
- `Terminals`
- `Quests`
- `Notes`
- หมวดอื่น ๆ
- ข้อมูลสำรองและไฟล์ JSON batches ใน `extracted/sheets/from_google/`
