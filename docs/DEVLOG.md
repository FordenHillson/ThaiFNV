# DEVLOG — บันทึกการพัฒนา ThaiFNV

เติมรายการใหม่ไว้**บนสุด** ทุกครั้งที่จบงานที่มีผลต่อสถานะโปรเจกต์  
รูปแบบ: `## YYYY-MM-DD — หัวข้อสั้น` แล้ว bullet สิ่งที่เปลี่ยน / เรียนรู้ / ไฟล์ที่แตะ

---

## 2026-11-06 — แก้ปัญหาข้อความชิดขอบล่างและสระล่างตกกรอบตัวเลือก (UI Hover Box & Baseline Lift Calibration)

- **ปัญหาข้อความจมชิดขอบล่างของกรอบเมาส์ Hover (Bottom-Hugging & Overflow):**
  - ในตัวเลือกบทสนทนา (Dialog Topics), รายชื่อเควสต์ใน Pip-Boy, ปุ่มยืนยัน (Confirmation Buttons เช่น "ใช่", "ออกเกม"), และแท็บ Pip-Boy ("World Map", "Quests") พบว่าข้อความลอยจมลงไปชิดเส้นขอบล่างของกรอบสี่เหลี่ยมสีเหลือง (`lb_highlight_box`) จนขอบบนมีช่องว่างโล่งมากเกินไป (19-40px)
  - สระล่าง (`ุ`, `ู`) ของคำเช่น `ขอบคุณ`, `ขุด`, `หลุม`, `กลับสู่รัง` ชนหรือทะลุเส้นขอบล่างของกรอบออกไป
- **การวิเคราะห์แก่นแท้ระบบ UI Gamebryo และ XML Templates:**
  - จากการแกะไฟล์ XML ทางการจาก `Fallout - Misc.bsa` (`dialog_menu.xml`, `message_menu.xml`, `list_box_template.xml`):
    - กรอบตัวเลือกสร้างจาก `<include src="list_box_template.xml"/>` โดยมีความสูงคำนวณจาก `item_height = font.line_height + _VerticalSpacing` (สำหรับ Dialog = 32 + 20 = 52px)
    - ตำแหน่งข้อความถูกกำหนดด้วย `<y> 15 </y>` (ในบทสนทนา) และ `<y> 20 </y>` (ในปุ่มกดยืนยัน)
    - Gamebryo วาง baseline ของบรรทัดแรกไว้ที่ `y + line_height` ซึ่งอยู่ห่างจากขอบล่างของกรอบเพียง **5px** เท่านั้น!
  - **สาเหตุที่ฟอนต์เดิม (Monofonto) แสดงผลได้:**
    - ฟอนต์ Monofonto ดั้งเดิมของเกมออกแบบมาให้ตัวพิมพ์ใหญ่สูงมาก (Ascent = 24..27px, Descent = 2..5px) ตัวอักษรจึงยืดขึ้นไปเต็มพื้นที่ด้านบนและลงมาแตะด้านล่างพอดี
    - ในขณะที่ฟอนต์ Sarabun ของไทย ขนาดตัวพยัญชนะมีความสูง 11..12px เพื่อเผื่อที่ให้สระบน/วรรณยุกต์ เมื่อนั่งอยู่บน baseline เดียวกันกับของเดิม พยัญชนะจึงจมลงไปอยู่ครึ่งล่างของกรอบ และสระล่าง `ุ`, `ู` ที่ยื่นลงมา 12..14px จึงล้นทะลุเส้นขอบล่างของกรอบ 5px
- **วิธีแก้ปัญหาที่สมบูรณ์แบบ — Universal Baseline Lift (+8.0px):**
  - เพิ่มพารามิเตอร์ `baseline_lift` ใน `pipeline/font_builder.py`
  - ใน Gamebryo การคำนวณตำแหน่ง quad บนหน้าจอคือ `screen_y = (baseline - g.ascent) + draw_y`
  - เมื่อกำหนด `g.ascent = float(m["asc"]) + baseline_lift`:
    - ตำแหน่งเรนเดอร์ของตัวอักษรทุกตัวบนหน้าจอจะถูก **ยกตัวลอยสูงขึ้นอย่างแม่นยำ +8.0px** เข้าสู่กึ่งกลางของกรอบไฮไลต์
    - สระล่าง `ุ`, `ู` ลอยพ้นเส้นขอบล่างขึ้นมามีระยะห่างปลอดภัย (Bottom Clearance) สบายตา 3-4px
    - พยัญชนะไทยทั่วไปอยู่กึ่งกลางกรอบตัวเลือกอย่างสมดุล (ระยะขอบบนและขอบล่างสมมาตร)
    - ระยะห่างระหว่างบรรทัด (Line Spacing) ของบทสนทนายังคงถูกควบคุมด้วย `line_height` อย่างอิสระ บรรทัดไม่ชนกัน 100%
- **การปรับแต่งในทุก Font Slots (VANILLA_SLOTS):**
  - Slot 1, 2, 4, 6, 7, 9 (ไซส์ 17-18): `baseline_lift = 8.0px`
  - Slot 3 (Glow_Monofonto_Medium, ไซส์ 15): `baseline_lift = 6.0px`
  - Slot 5 (Fixedsys_Comp_uniform_width, ไซส์ 20): `baseline_lift = 4.0px`
  - Slot 8 (Glow_Futura_Caps_Large, ไซส์ 36): `baseline_lift = 12.0px`
- **ไฟล์และแพ็กเกจที่เกี่ยวข้อง:**
  - `pipeline/font_builder.py` (เพิ่ม `baseline_lift`, อัปเดต `VANILLA_SLOTS` และ `main()`)
  - อัปเดตและ Deploy ฟอนต์ทั้ง 9 รายการไปยัง `Data\Textures\Fonts\` ในโฟลเดอร์เกม
  - สร้างแพ็กเกจม็อดเวอร์ชันใหม่:
    - `release/ThaiFNV_v2.2_CenteredBoxes.zip`
    - `C:\Users\saetanpee\Desktop\ThaiFNV_v2.2_CenteredBoxes.zip`


## 2026-11-06 — การปรับปรุงระยะช่องไฟอักษร (Letter Spacing) และ Thai Shaper Engine v2.1 สำเร็จสมบูรณ์

- **ปัญหาช่องไฟ (Letter Spacing / Tracking):**
  - ในการปรับรอบก่อน พยัญชนะทั่วไปถูกตัด advance ชิดเกินไปจนเส้น stroke outline (1px) เกยทับกัน (-1.0px) ทำให้ข้อความดูทึบและอึดอัด
  - สระหน้า (`ไ`, `ใ`, `โ`) ถูกคำนวณ advance จากความกว้างกล่องทั้งหมด (`ink_w + 1.0`) ซึ่งรวมหางที่ยื่นไปทางซ้าย (`left_ink < 0`) ส่งผลให้เกิดช่องว่างหลอกตา 4-5px ก่อนพยัญชนะต้น เช่น `ไ ป`, `เ ลย`, `แ ข็ง`
- **การแก้ไขและสูตรปรับ Advance สม่ำเสมอ (Uniform Right-Ink Advance):**
  - กำหนดตำแหน่งขอบขวาจริงของหมึก: $\text{right\_ink} = \text{left\_ink} + \text{ink\_w}$
  - กำหนด advance ให้ก้าวพ้นขอบขวาจริง **+1.0px** เท่ากันทุกตัวอักษร: $\text{adv} = \text{round\_adv}(\text{right\_ink} + 1.0)$
  - ส่งผลให้พยัญชนะทุกตัวมีระยะหายใจระหว่างเส้นขอบ 1.0px พอดี สระหน้าแนบสนิทกับพยัญชนะต้นอย่างเป็นธรรมชาติ ไม่ทับซ้อนและไม่มีช่องว่างเกิน
- **การจัดระดับสระและวรรณยุกต์ (Vertical Offsets & Clearance):**
  - ยกระดับสระบน (`ิ, ี, ึ, ื, ั, ็, ํ, ๎`) และวรรณยุกต์เดี่ยวขึ้น **+2.5px**
  - เลื่อนสระล่าง (`ุ, ู, ฺ`) ลง **-2.5px** ไม่เกยทับฐานพยัญชนะ
  - วรรณยุกต์ซ้อนสระบน 2 ชั้น (`0x80..0x9B` เช่น `ี่`, `ั้`, `ิ้`) ย่อขนาดลง 80% และเว้น `tone_gap = 2.5px` ขอบเส้นคมชัด อ่านง่าย ไม่ทึบหนา
- **สระอำ (`ำ` - 0xD3):**
  - ปรับใช้ Precomposed Single Glyph `0xD3` เต็มระบบ
  - จัด `bearing_x = left_ink - pad_x` ให้จุดนิคหิตถอยไปวางบนเสาขวาของพยัญชนะหน้า และชดเชย `adv = round_adv(right_ink + 1.0) - bx` ให้ pen ก้าวพ้นขอบสระอา 1.0px พอดี
- **เครื่องมือ Vit-o-matic Vigor Tester (Texture & 3D Tool):**
  - พัฒนา `pipeline/vigor_tester_tool.py` และ `tools/vigor_tester_viewer.html`
  - สกัด texture DDS จาก BSA ทั้งหมดของตู้ทดสอบพลัง (หน้า 0-4 และ special values) แปลงเป็น PNG พร้อมตัวพรีวิว 3D Interactive (Three.js) และตัวแปลงกลับเป็น DXT5 DDS ด้วยคำสั่งเดียว
- **ผลการทดสอบในเกม:**
  - ยืนยันผลลัพธ์ผ่านบทสนทนาจริงของ Doc Mitchell ในเกม Fallout: New Vegas อักษรไทยทุกตัวจัดวางสวยงาม สมดุล ชัดเจน สบายตา ไร้บั๊กทับซ้อน
- **ไฟล์ที่เกี่ยวข้อง:**
  - `pipeline/font_builder.py`
  - `pipeline/thai_shaper_engine.py`
  - `pipeline/vigor_tester_tool.py`
  - `tools/vigor_tester_viewer.html`
  - `release/ThaiFNV_v2.1_SpacingFix.zip` และสำเนาบน Desktop

## 2026-11-06 — บทเรียนสำคัญ: ห้ามแพตช์ FalloutNV.exe โดยตรง (Steam Error 3:0000065432)

- **ปัญหา:** การใช้ `patch_main_menu_exe.py` ไปแก้ไขไบนารีสตริงใน `FalloutNV.exe` ทำให้ระบบ DRM SteamStub ของ Steam พัง และเกมเด้งด้วยข้อผิดพลาด:
  `Steam Error: Application load error 3:0000065432`
- **การแก้ไข:** Restore `FalloutNV.exe` กลับคืนสภาพ Official Steam แท้ทันที
- **บันทึกกฎถาวร:** บันทึกลง `GEMINI.md` ห้ามแตะต้องไฟล์ `.exe` เด็ดขาด ม็อดทั้งหมดต้องทำงานผ่าน `ThaiFNV.esp` และ `Textures\Fonts\` หรือ NVSE เท่านั้น


## 2026-11-05 — รื้อถอนระบบ Font และ Data Extraction เดิม เพื่อเริ่มต้นออกแบบใหม่

- สำรองโค้ดและประวัติการทำงานเดิมทั้งหมดไว้ที่ Git branch `archive/legacy-font-and-extract`
- ลบส่วนงานฟอนต์เดิม: `fonts/`, สคริปต์ `font_*.py`, `fnt_lib.py`, `testing/`, `scratch/` และเอกสารฟอนต์ทั้งหมด
- ลบส่วนงานสกัดและฉีดข้อมูลเดิม: `fnv_esm.py`, `make_categories.py`, `Tools/`, สคริปต์ compile ESP
- ลบ `Rule.md` ตามคำขอ
- คงข้อมูลการแปลทั้งหมดไว้ใน `corpus/` และ `extracted/sheets/` เพื่อนำไปใช้กับสถาปัตยกรรมใหม่


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
