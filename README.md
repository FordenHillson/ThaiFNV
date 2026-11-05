# ThaiFNV

Mod แปลภาษาไทยสำหรับ **Fallout: New Vegas**

> โปรเจกต์อยู่ในช่วงรีเซ็ตและออกแบบระบบ Font / Extraction / Packaging ใหม่ตั้งแต่ศูนย์ โดยเก็บรักษาฐานข้อมูลแปลเดิมไว้ครบถ้วน (ประวัติระบบเดิมถูกสำรองไว้ใน branch `archive/legacy-font-and-extract`)

## ข้อมูลที่คงไว้ใน Repository

- **ข้อมูลการแปล (Corpus & Translations)**:
  - `corpus/names_glossary_short.md` — คลังคำศัพท์และชื่อเฉพาะ
  - `corpus/sheets_backup/` — สำรองข้อมูล CSV จาก Google Sheets
  - `corpus/google_sheets/` — เครื่องมือเชื่อมต่อ Google Sheets และ MT Dashboard
  - `extracted/sheets/` — ชุดข้อมูลแปลแยกตามหมวดหมู่
  - `.superpowers/` — ข้อมูลและรายงานการแปลชื่อ
- **Scripts เชื่อมต่อการแปล**:
  - สคริปต์ Sync ข้อมูลกับ Google Sheets / MT Bridge ใน `pipeline/` และ `scripts/`

## สถานะปัจจุบัน

- รื้อระบบ Font Renderer / Builder และ ESM Extraction เดิมออกทั้งหมด เพื่อเตรียมออกแบบสถาปัตยกรรมใหม่
- ข้อมูลและโค้ดรุ่นก่อนหน้าถูก snapshot ไว้ที่ Git branch `archive/legacy-font-and-extract`
