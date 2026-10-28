# บันทึกงาน Phase 0 (2026-10-28)

## สิ่งที่เสร็จแล้ว
1. **สร้าง workspace + git**: D:\backup\github\ThaiFNV (git init, branch main) — commit `4254f6e` เก็บ plan.md + .gitignore
2. **แก้จุดพังฟอนต์เดิม**:
   - สำรวจพบ: FalloutPrefs.ini ชี้ฟอนต์ไทยชุดเก่า (NVfontsv2 / NVFontmaitermi / NVFontmai33 / NVFont) ที่ไฟล์ไม่มีอยู่ใน Data แล้ว
   - ไฟล์ที่แก้: C:\Users\saetanpee\Documents\My Games\FalloutNV\FalloutPrefs.ini (5 บรรทัด [Fonts])
   - แก้เป็นค่า vanilla ตาม Fallout.ini:
     - slot 1: NVfontsv2.fnt → Glow_Monofonto_Large.fnt
     - slot 3: NVfontsv2.fnt → Glow_Monofonto_Medium.fnt
     - slot 5: NVFontmaitermi.fnt → Fixedsys_Comp_uniform_width.fnt
     - slot 8: NVFontmai33.fnt → Glow_Futura_Caps_Large.fnt
     - slot 9: NVFont.fnt → NVFont_Test.fnt
   - Backup ของเดิมเก็บไว้ที่: testing\ini-backups\FalloutPrefs.ini.bak-2026-10-28
   - ไม่แตะ Fallout.ini (ค่า vanilla ถูกอยู่แล้ว) และ FalloutCustom.ini (ไม่มีการตั้งฟอนต์)

## ข้อสังเกตจากการตรวจ ini
- FalloutPrefs.ini มีขนาด ~24 KB (line ~503+ รวม [Fonts])
- FalloutCustom.ini ขนาด 28 ไบต์ ไม่มีการตั้งฟอนต์ — ปล่อยไว้
- หน้าจอเครื่องคุณ: 2560x1440 (RTX 4070 Ti SUPER)

## การตัดฟอนต์ DarN
- Data\Textures\fonts ตอนนี้มี vanilla 4 ชื่อ + DarN 5 ไฟล์ที่มาจาก DarNifiedUINV
- สตลิงภายใน Monofonto_Large.fnt พบชื่อ DarN_FranKleinBold_16 → DarNified UI ทับ slot บางช่อง
- แผน: เฟส font prototype จะที่วางแผน "ตัว glyph Thai" ลงใน slot ที่กล่องบทสนทนาใช้ — ระวังชนกับ DarN

## หมายเหตุเทคนิค
- ระบบ ini อ่านจาก Fallout.ini รวม + FalloutPrefs.ini (ปัจจุบัน Prefs ทับตามต่างบางจุด)
- การแก้ ini ใช้ Python อ่านเขียนแบบ latin-1 (byte-preserving) คุมอยู่

## ต่อไป
- ติดตั้ง xTranslator และ FNVEdit (จะสร้าง links เราจะ คู่มือ)
- จากนั้น: export ข้อความ FalloutNV.esm → pipeline → Google Sheets
