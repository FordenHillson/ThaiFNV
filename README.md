# ThaiFNV

Mod แปลภาษาไทยสำหรับ **Fallout: New Vegas** — ฟอนต์ไทยครบสล็อต + แปลข้อความเกมหลัก (และจะขยายไป DLC / YUP / mod ใหญ่)

> โปรเจกต์ยังอยู่ในขั้นพัฒนา — ยังไม่มีแพ็กเกจติดตั้งสำหรับผู้เล่นทั่วไป

## สถานะสั้น ๆ

- **ฟอนต์**: Sarabun Bold (CP874) พร้อม outline — ทดสอบในเกมแล้ว (vanilla + DarNified UI patch)
- **ข้อความ**: extract จาก `FalloutNV.esm` ครบหมวด (~67k แถว) — กำลังเข้าสู่ MT seed + post-edit
- **แพ็กเกจ**: ยังไม่ทำ FOMOD

รายละเอียดสำหรับคน/ agent ที่มาทำงานต่อ → **[CONTEXT.md](CONTEXT.md)**  
แผนเฟสเต็ม → [plan.md](plan.md) · ความคืบหน้า → [docs/STATUS.md](docs/STATUS.md) · บันทึกงาน → [docs/DEVLOG.md](docs/DEVLOG.md)

## ความต้องการของเครื่องพัฒนา

- Fallout: New Vegas (Steam) + DLC ตามที่ต้องการทดสอบ
- Python 3.10+ พร้อม `Pillow`, `fontTools` (สำหรับ build ฟอนต์)
- [xTranslator](https://www.nexusmods.com/starfield/mods/313) และ [FNVEdit](https://www.nexusmods.com/newvegas/mods/128) — วางใน `pipeline/xtranslator/` และ `pipeline/fnvedit/` (ไม่รวมใน git)

## คำสั่งที่ใช้บ่อย

```bash
# สร้างฟอนต์ vanilla / DarN
python pipeline/font_builder.py --ttf fonts/src/Sarabun-Bold.ttf --batch vanilla --out-dir fonts/out/vanilla
python pipeline/font_builder.py --ttf fonts/src/Sarabun-Bold.ttf --batch darn --out-dir fonts/out/darn

# ตรวจ .fnt/.tex ก่อนติดตั้ง
python pipeline/font_check.py fonts/out/vanilla/Glow_Monofonto_Large.fnt

# Extract ข้อความจาก ESM (ชี้ path Data ของเกม)
python pipeline/fnv_esm.py "D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\FalloutNV.esm" --out extracted/FalloutNV_extract_v1.csv

# แยกหมวดสำหรับ Google Sheets
python pipeline/make_categories.py extracted/FalloutNV_extract_v1.csv --out-dir extracted/sheets
```

คู่มือ pipeline เต็ม → [pipeline_guide.md](pipeline_guide.md)

## โครงสร้างหลัก

| โฟลเดอร์ | เนื้อหา |
|---|---|
| `pipeline/` | สคริปต์ Python |
| `fonts/` | TTF ต้นทาง + `.fnt/.tex` ที่ build แล้ว |
| `extracted/` | CSV ข้อความจากเกม |
| `docs/` | บันทึกวิจัยและสถานะพัฒนา |
| `release/` | zip แจกจ่าย (ยังว่าง) |

## ลิขสิทธิ์ / เครดิต

- เกมและข้อความต้นฉบับ © Bethesda Softworks — โปรเจกต์นี้เป็นงานแปล/mod ของแฟน ไม่ใช่ผลิตภัณฑ์ทางการ
- ฟอนต์ **Sarabun** — [SIL Open Font License](fonts/src/LICENSE-Sarabun.txt)
- อ้างอิงแนวทาง: [FNV_THAI](https://www.nexusmods.com/newvegas/mods/98964), Cobb's Oblivion Font Editor, OpenMW font loader

## กติกาสำหรับ AI agent

อ่าน [Rule.md](Rule.md) ก่อนลงมือ — ทำเท่าที่สั่ง, ถามเมื่อไม่ชัด, เสร็จแล้วรอผู้ใช้ตรวจ
