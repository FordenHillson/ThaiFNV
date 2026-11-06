# ThaiFNV — Core Development Rules & Memory

## ⚠️ กฎเหล็ก: ห้ามแก้ไข/แพตช์ไฟล์ `FalloutNV.exe` โดยตรงเด็ดขาด
- **Error ที่เกิดขึ้น:** การแก้ไขไบนารีใน `FalloutNV.exe` บนเวอร์ชัน Steam จะทำให้ระบบ SteamStub DRM ตรวจพบความผิดปกติ ส่งผลให้เกม Crash ทันทีด้วย:
  `Steam Error: Application load error 3:0000065432`
- **ข้อพึงปฏิบัติ:**
  1. `FalloutNV.exe` ต้องคงสภาพ Original Steam Official เสมอ ห้ามรันสคริปต์ hex patch หรือ byte patch ใส่ exe เด็ดขาด
  2. การแปลภาษาและระบบจัดรูปอักขระ (Thai Shaper Engine) ทั้งหมด ต้องทำผ่าน:
     - ไฟล์ม็อดข้อมูล: `ThaiFNV.esp`
     - ไฟล์ฟอนต์: `Data\Textures\Fonts\*.fnt` และ `*.tex`
     - หรือ NVSE Memory Hooking เท่านั้น
  3. ข้อความปุ่มเมนูหลักตอนเปิดเกม (Continue, New, Load, Settings, Credits, Quit) ถูกฮาร์ดโค้ดใน exe ดั้งเดิม ตัวม็อด `ThaiFNV.esp` จะเริ่มทำงานเต็มรูปแบบทันทีเมื่อผู้เล่นกด New หรือ Load เข้าสู่ตัวเกม
