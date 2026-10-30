# ThaiFNV — Context สำหรับ agent / คนทำงาน

Mod แปลภาษาไทยสำหรับ **Fallout: New Vegas**  
workspace: `D:\backup\github\ThaiFNV`  
อ่านคู่กับ `Rule.md` ทุก session

---

## โปรเจกต์นี้คืออะไร

แพ็กเกจ mod ที่:
1. แสดงอักษรไทยในเกมได้ (bitmap font 9 สล็อต + DarN patch)
2. แปลข้อความเกมหลัก → DLC → YUP → mod ใหญ่ ตามลำดับ
3. ติดตั้งผ่าน FOMOD (Vortex / MO2)

ข้อความเกมฝังใน `.esm/.esp` (ไม่มี `.strings`) — ใช้ encoding **CP874 / TIS-620** ในตาราง glyph 256 ช่อง

---

## สถานะปัจจุบัน (อัปเดตเมื่อเปลี่ยนเฟส)

| หัวข้อ | สถานะ |
|---|---|
| Phase 0 (workspace, ini cleanup) | เสร็จ |
| ฟอนต์ Sarabun Bold + outline (vanilla + DarN) | ใช้งานได้ในเกม — ปรับขนาดรอบล่าสุด 2026-10-28 |
| Extract ข้อความ FalloutNV.esm | เสร็จ (~67k แถว แยกหมวดใน `extracted/sheets/`) |
| MT seed / Google Sheets | มี Apps Script + Messages แปลทดลอง |
| ป้อนแปลกลับเข้า ESM | ยังไม่ทำ |
| FOMOD / แพ็กเกจแจก | ยังไม่ทำ |

รายละเอียดเฟสและแผนเต็ม → `plan.md`  
บันทึกความคืบหน้ารายวัน → `docs/DEVLOG.md`  
สถานะสั้น ๆ ที่อัปเดตบ่อย → `docs/STATUS.md`

---

## โครงสร้างโฟลเดอร์

```
ThaiFNV/
├── CONTEXT.md          ← ไฟล์นี้ (อ่านก่อนทำงาน)
├── Rule.md             ← กติกา agent (ทำเท่าที่สั่ง / ถามเมื่อไม่ชัด / รอผู้ใช้ตรวจ)
├── README.md           ← ภาพรวมสำหรับคน
├── plan.md             ← แผนฉบับทำงาน (phases, decisions, ความเสี่ยง)
├── pipeline_guide.md   ← คู่มือรัน pipeline จริง
├── docs/               ← บันทึกวิจัย + DEVLOG + STATUS
├── pipeline/           ← สคริปต์ Python (ฟอนต์ + extract)
│   ├── fnt_lib.py      ← codec .fnt/.tex
│   ├── font_builder.py ← สร้างชุดฟอนต์จาก TTF (CP874)
│   ├── font_check.py / font_render.py / font_patch.py
│   ├── fnv_esm.py      ← extract ข้อความจาก ESM
│   ├── make_categories.py
│   ├── bsa_extract.py
│   ├── fnvedit/        ← เครื่องมือภายนอก (ไม่ commit)
│   └── xtranslator/    ← เครื่องมือภายนอก (ไม่ commit)
├── fonts/
│   ├── src/            ← Sarabun TTF + LICENSE
│   ├── atlas/          ← PNG ระหว่างสร้าง
│   └── out/vanilla|darn/  ← .fnt/.tex พร้อมใช้
├── extracted/          ← CSV จาก extract (+ sheets แยกหมวด)
├── corpus/             ← glossary / backup ชีต / สิทธิ์
├── release/            ← zip แจกจ่าย
└── testing/            ← ไฟล์ทดสอบ, capture scripts (png ชั่วคราว gitignore)
```

---

## Decisions ที่ล็อกแล้ว

| หัวข้อ | ค่า |
|---|---|
| Encoding ข้อความไทยในเกม | CP874 (byte 0xA1–0xFB) |
| ฟอนต์ต้นแบบ | Sarabun Bold + baked outline `#6A5C40` / `#B0A078` |
| ชื่อไฟล์ฟอนต์ | ชื่อ vanilla drop-in (ไม่แก้ INI ของผู้ใช้) |
| DIAL topic names | แปลด้วย |
| DarNified UI | patch แยกใน FOMOD |
| กลยุทธ์แปล | MT seed (Sheets) → human post-edit |
| ขอบเขตเริ่ม | FalloutNV.esm ก่อน แล้ว DLC → YUP → mod |

---

## ฟอนต์ — ข้อเท็จจริงสำคัญ

- `.fnt` = header 296 B + 256 glyph × 56 B; `.tex` = RGBA atlas
- UV = 4 มุม (L,T)/(R,T)/(L,B)/(R,B) — **ห้ามสลับแกน** (ดู `docs/2026-10-28-fnt-format-fix.md`)
- Combining ไทย: `advance=0` + `bearing_x` ติดพยัญชนะก่อนหน้า
- Justify เมนู: `bearing_x=0` สำหรับ non-combining + `advance` เป็นจำนวนเต็ม
- ขนาดปัจจุบัน (vanilla): 21/20/18/20/24/21/21/42/31 px — รายละเอียดใน `font_builder.FONTSETS`
- Build:
  ```
  python pipeline/font_builder.py --ttf fonts/src/Sarabun-Bold.ttf --batch vanilla --out-dir fonts/out/vanilla
  python pipeline/font_builder.py --ttf fonts/src/Sarabun-Bold.ttf --batch darn --out-dir fonts/out/darn
  ```

---

## Extract ข้อความ — ตัวเลขล่าสุด (FalloutNV.esm)

| หมวด | แถวโดยประมาณ |
|---|---|
| Dialogue (INFO NAM1) | 29,634 |
| TopicNames (DIAL FULL) | 18,176 |
| Names | 13,177 |
| Messages | 1,958 |
| Terminals | 1,987 |
| Quests | 1,400 |
| Notes | 1,019 |
| อื่น ๆ | <500 |

คอลัมน์ชีต: `ID | ประเภท | FormID | EditorID | EN | TH | สถานะ | หมายเหตุ`

---

## เอกสารที่ต้องอ่านตามงาน

| งาน | อ่าน |
|---|---|
| กฎการทำงาน agent | `Rule.md` |
| แผนเฟส / ความเสี่ยง | `plan.md` |
| รันสคริปต์ pipeline | `pipeline_guide.md` |
| บั๊ก/รูปแบบ .fnt | `docs/2026-10-28-fnt-format-fix.md` |
| ขนาดฟอนต์ / outline | `docs/2026-10-28-bold-outline-and-size-calibration.md` |
| Phase 0 ini | `docs/2026-10-28-phase0-ini-cleanup.md` |
| ความคืบหน้าล่าสุด | `docs/STATUS.md` + `docs/DEVLOG.md` |

---

## สิ่งที่ห้าม commit

- `pipeline/fnvedit/`, `pipeline/xtranslator/` (binary เครื่องมือภายนอก)
- `testing/vanilla_bsa_fonts/` (asset Bethesda)
- `testing/*.png` (ภาพจับหน้าจอชั่วคราว)
- โฟลเดอร์เกม / save / `.esm` ต้นฉบับ
- โฟลเดอร์ขยะจากคำสั่ง shell (`-Force`, `-p`, `pipeline]`)

---

## Next (ลำดับงานถัดไปตามแผน)

1. ยืนยัน/ขยาย MT seed บน Google Sheets + Glossary
2. Human post-edit หมวด Messages / Names ก่อน
3. Pipeline CSV → ป้อนกลับ ESM (CP874) + round-trip test
4. ประกอบ FOMOD + ทดสอบ Vortex/MO2
5. ขยาย DLC / YUP / major mods

เมื่อเปลี่ยนสถานะเฟส: อัปเดตตารางในไฟล์นี้ + `docs/STATUS.md` + เติมบรรทัดใน `docs/DEVLOG.md`
