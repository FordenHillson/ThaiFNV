# ThaiFNV — ข้อมูลการแกะข้อความเกม (Game Text Extraction Manifest)

สกัดข้อความทั้งหมดจาก **Fallout: New Vegas** ตัวเต็ม พร้อม DLC ครบทั้ง 9 ตัว  
วันที่แกะข้อมูล: `2026-11-05 19:53:59`  
จำนวนข้อความทั้งหมด: **90,074 รายการ**  
การระบุชื่อตัวละครในบทสนทนา (Dialogue Speaker Resolution): **35,604 / 39,115 (91.0%)**

---

## 1. ข้อมูลแยกตามหมวดหมู่ (By Category)

ไฟล์ทั้งหมดเก็บอยู่ที่: `extracted/by_category/` และ `extracted/sheets/`

| ชื่อไฟล์ | หมวดหมู่ | ชนิด Record ในเกม | จำนวนแถว |
|---|---|---|---:|
| `FNV_Dialogue.csv` | บทสนทนา (Dialogue) | `INFO` (NAM1 คำพูด, RNAM ช้อยส์) | 39,115 |
| `FNV_TopicNames.csv` | หัวข้อบทพูดในเมนู | `DIAL` (FULL) | 21,521 |
| `FNV_Quests.csv` | เควสและเป้าหมาย | `QUST` (FULL ชื่อเควส, NNAM เป้าหมาย) | 1,974 |
| `FNV_Messages.csv` | ป๊อปอัป, กล่องข้อความ, ปุ่มกดยืนยัน | `MESG` (FULL, DESC, ITXT) | 2,950 |
| `FNV_Terminals.csv` | จอคอมพิวเตอร์เทอร์มินัล | `TERM` (FULL, DESC, ITXT, RNAM) | 3,357 |
| `FNV_Notes.csv` | บันทึก, จดหมาย, ข้อความเทป | `NOTE` (FULL, TNAM) | 2,226 |
| `FNV_Books.csv` | หนังสือ และนิตยสารสกิล | `BOOK` (FULL, DESC) | 46 |
| `FNV_Items.csv` | อาวุธ, ชุดเกราะ, ยา, กระสุน, ขยะ, กุญแจ | `WEAP`, `ARMO`, `ALCH`, `AMMO`, `MISC` ฯลฯ | 3,120 |
| `FNV_Perks_Skills.csv` | Perks, Traits, SPECIAL, เวทมนตร์, ชาเลนจ์ | `PERK`, `AVIF`, `SPEL`, `MGEF`, `CHAL` ฯลฯ | 1,973 |
| `FNV_World_Objects.csv` | ชื่อ NPC, มอนสเตอร์, ฝ่าย, สถานที่, ประตู, กล่อง | `NPC_`, `CREA`, `FACT`, `CELL`, `WRLD` ฯลฯ | 11,871 |
| `FNV_LoadScreens.csv` | ข้อความ Lore หน้าโหลดเกม | `LSCR` (DESC) | 283 |
| `FNV_GameSettings.csv` | ข้อความระบบ UI ฮาร์ดโค้ด (Yes, No, Take All...) | `GMST` (DATA) | 129 |
| `FNV_Other.csv` | ข้อความอื่น ๆ | เผ่าพันธุ์, คลาส ฯลฯ | 1,509 |
| **รวมทั้งหมด** | | | **90,074** |

---

## 2. ข้อมูลแยกตาม DLC (By DLC)

นอกจากระบุคอลัมน์ `DLC` และ `Plugin` ในทุกบรรทัดของไฟล์หมวดหมู่แล้ว ยังแยกโฟลเดอร์ให้อยู่ใน `extracted/by_dlc/` ดังนี้:

| โฟลเดอร์ใน `extracted/by_dlc/` | DLC | ไฟล์ Plugin | จำนวนข้อความ |
|---|---|---|---:|
| `Base_Game/` | Fallout: New Vegas (ตัวหลัก) | `FalloutNV.esm` | 70,586 |
| `Dead_Money/` | Dead Money (DLC 1) | `DeadMoney.esm` | 6,753 |
| `Honest_Hearts/` | Honest Hearts (DLC 2) | `HonestHearts.esm` | 3,679 |
| `Old_World_Blues/` | Old World Blues (DLC 3) | `OldWorldBlues.esm` | 5,300 |
| `Lonesome_Road/` | Lonesome Road (DLC 4) | `LonesomeRoad.esm` | 3,405 |
| `Gun_Runners_Arsenal/` | Gun Runners' Arsenal | `GunRunnersArsenal.esm` | 331 |
| `Courier_Stash/` | Classic / Caravan / Mercenary / Tribal Packs | `*.esm` | 20 |

---

## 3. รายละเอียดคอลัมน์ของไฟล์บทพูด (`FNV_Dialogue.csv`)

โครงสร้างข้อมูลถูกออกแบบมาเพื่อให้นักแปลเข้าใจบริบท น้ำเสียง และสไตล์การพูดของแต่ละตัวละครได้อย่างแม่นยำ:

- **`DLC`**: ระบุ DLC ชัดเจน (เช่น `Dead Money`, `Honest Hearts`, `Base Game`)
- **`Plugin`**: ชื่อไฟล์ `.esm` ต้นฉบับ
- **`FormID`**: FormID ในเกม สำหรับใช้อ้างอิงและอิมพอร์ตกลับเข้า mod
- **`ResponseIndex`**: ลำดับประโยคพูดในเหตุการณ์นั้น (1, 2, 3...)
- **`Speaker`**: **ชื่อตัวละครที่พูด** (เช่น `Doc Mitchell`, `Father Elijah`, `Joshua Graham`, `Craig Boone`, `Veronica`, `Ulysses`, `Doctor Dala` หรือกลุ่มฝ่ายเช่น `[Faction: Boulder City Great Khans]`)
- **`Speaker_ID`**: FormID / EditorID ของตัวละคร
- **`Speaker_Type`**: แหล่งที่มาของการระบุ (`Actor (ANAM)`, `Actor (Condition)`, `Faction`, `VoiceType`, `Player`)
- **`Emotion`**: อารมณ์และระดับความรู้สึกของตัวละครที่เกมตั้งไว้ เช่น `Anger (50)`, `Disgust (20)`, `Happy (50)`, `Sad (50)`, `Surprise (50)`, `Fear (50)`, `Neutral (50)`
- **`ActorNotes`**: โน้ตกำกับเสียงพากย์ของทีมเขียนบท Obsidian (เช่น `[Whispering]`, `[Sarcastic]`, `[Angry] Slower at the end...`)
- **`Topic_Name` & `Topic_EDID`**: ชื่อหัวข้อบทสนทนา
- **`Quest_Name` & `Quest_EDID`**: ชื่อเควสที่เป็นเจ้าของบทสนทนานี้
- **`EN`**: ข้อความภาษาอังกฤษต้นฉบับ
- **`TH`**: ช่องสำหรับแปลภาษาไทย (เว้นว่างไว้ตามคำขอ)
- **`Status`**: สถานะการแปล
- **`Notes`**: หมายเหตุเพิ่มเติมของนักแปล
