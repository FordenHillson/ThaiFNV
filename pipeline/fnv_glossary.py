#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fnv_glossary.py — คลังศัพท์มาตรฐานและแนวทางการแปลสำหรับ Fallout: New Vegas (ThaiFNV)
"""

# คำศัพท์เฉพาะและชื่อเฉพาะที่ต้องคงเส้นคงวา (Fallout New Vegas Glossary)
FNV_TERMS: dict[str, str] = {
    # Factions & Groups
    "New California Republic": "สาธารณรัฐแคลิฟอร์เนียใหม่",
    "NCR": "เอ็นซีอาร์",
    "Caesar's Legion": "ลีเจียนของซีซาร์",
    "The Legion": "เดอะลีเจียน",
    "Brotherhood of Steel": "บราเธอร์ฮูดออฟสตีล",
    "Great Khans": "เกรตคานส์",
    "Boomers": "บูมเมอร์ส",
    "Powder Gangers": "พาวเดอร์แกงเกอร์ส",
    "Fiends": "ฟีนด์ส",
    "Followers of the Apocalypse": "ผู้ติดตามแห่งวันสิ้นโลก",
    "Enclave": "เอนเคลฟ",
    "Chairmen": "แชร์แมน",
    "Omertas": "โอเมอร์ทา",
    "White Glove Society": "สมาคมถุงมือขาว",

    # Major Characters & Titles
    "Courier": "คนส่งของ / เดอะคูเรียร์",
    "Mr. House": "มิสเตอร์เฮาส์",
    "Yes Man": "เยสแมน",
    "Legate Lanius": "เลเกต ลานิอุส",
    "Father Elijah": "ฟาเธอร์ เอไลจาห์",
    "Joshua Graham": "โจชัว เกรแฮม",
    "Burned Man": "ชายผู้ถูกเผา",
    "Ulysses": "ยูลิสซิส",
    "Doc Mitchell": "ด็อก มิตเชลล์",
    "Sunny Smiles": "ซันนี่ สไมล์ส",
    "Craig Boone": "เครก บูน",
    "Veronica": "เวโรนิกา",
    "Raul": "ราอูล",
    "Arcade Gannon": "อาร์เคด แคนนอน",
    "Rose of Sharon Cassidy": "แคสส์",
    "Lily": "ลิลี่",

    # Key Locations
    "Mojave Wasteland": "แดนรกร้างโมฮาวี",
    "Wasteland": "แดนรกร้าง",
    "New Vegas": "นิวเวกัส",
    "The Strip": "เดอะสตริป",
    "Freeside": "ฟรีไซด์",
    "Goodsprings": "กู๊ดสปริงส์",
    "Novac": "โนแวค",
    "Primm": "พริมม์",
    "Boulder City": "โบลเดอร์ซิตี",
    "Hoover Dam": "เขื่อนฮูเวอร์",
    "Lucky 38": "ลัคกี้ 38",
    "Sierra Madre": "เซียร่า มาเดร",
    "Zion Canyon": "หุบเขาไซออน",
    "Big MT": "บิ๊กเอ็มที",
    "The Divide": "เดอะดีไวด์",

    # Items & Gameplay Concepts
    "Vault": "วอลต์",
    "Vault-Tec": "วอลต์-เทค",
    "Pip-Boy": "พิปบอย",
    "Caps": "ฝา / แคปส์",
    "Bottle Cap": "ฝาขวด",
    "Bottle Caps": "ฝาขวด",
    "Stimpak": "สติมแพก",
    "Super Stimpak": "ซูเปอร์สติมแพก",
    "RadAway": "เรดอะเวย์",
    "Rad-X": "เรด-เอ็กซ์",
    "Med-X": "เมด-เอ็กซ์",
    "Jet": "เจ็ท",
    "Psycho": "ไซโค",
    "Buffout": "บัฟเอาต์",
    "Stealth Boy": "สเตลท์บอย",
    "Sunset Sarsaparilla": "ซันเซ็ต ซาร์ซาพาริลลา",
    "Nuka-Cola": "นูกา-โคล่า",
    "Caravan": "คาราวาน",
    "V.A.T.S.": "V.A.T.S.",
    "Hardcore Mode": "โหมดฮาร์ดคอร์",

    # Creatures & Races
    "Ghoul": "กูล",
    "Feral Ghoul": "กูลคลั่ง",
    "Super Mutant": "ซูเปอร์มิวแทนท์",
    "Nightkin": "ไนท์คิน",
    "Deathclaw": "เดธคลอว์",
    "Cazador": "คาซาดอร์",
    "Gecko": "เก็กโค",
    "Molerat": "โมลแรท",
    "Brahmin": "บราห์มิน",
    "Bighorner": "บิ๊กฮอร์นเนอร์",
    "Radscorpion": "เรดสคอร์เปียน",
    "Securitron": "ซีเคียวริตรอน",
    "Lobotomite": "โลโบโทไมท์",

    # S.P.E.C.I.A.L. & Skills
    "Strength": "พละกำลัง (Strength)",
    "Perception": "การรับรู้ (Perception)",
    "Endurance": "ความทรหด (Endurance)",
    "Charisma": "เสน่ห์ (Charisma)",
    "Intelligence": "สติปัญญา (Intelligence)",
    "Agility": "ความคล่องตัว (Agility)",
    "Luck": "โชค (Luck)",
    "Barter": "การค้าขาย (Barter)",
    "Energy Weapons": "อาวุธพลังงาน (Energy Weapons)",
    "Explosives": "วัตถุระเบิด (Explosives)",
    "Guns": "อาวุธปืน (Guns)",
    "Lockpick": "การสะเดาะกลอน (Lockpick)",
    "Medicine": "การแพทย์ (Medicine)",
    "Melee Weapons": "อาวุธระยะประชิด (Melee Weapons)",
    "Repair": "การซ่อมแซม (Repair)",
    "Science": "วิทยาศาสตร์ (Science)",
    "Sneak": "การลอบเร้น (Sneak)",
    "Speech": "การเจรจา (Speech)",
    "Survival": "การเอาชีวิตรอด (Survival)",
    "Unarmed": "มือเปล่า (Unarmed)",

    # UI & Controls
    "Continue": "เล่นต่อ",
    "New": "เริ่มเกมใหม่",
    "Load": "โหลดเซฟ",
    "Save": "บันทึกเกม",
    "Settings": "การตั้งค่า",
    "Credits": "เครดิต",
    "Downloadable Content": "เนื้อหาดาวน์โหลด (DLC)",
    "Quit": "ออกจากเกม",
    "Exit Game": "ออกจากเกม",
    "Main Menu": "เมนูหลัก",
    "Gameplay": "การเล่น",
    "Display": "การแสดงผล",
    "Audio": "เสียง",
    "Controls": "การควบคุม",
    "Brightness": "ความสว่าง",
    "HUD Opacity": "ความทึบแสง HUD",
    "Subtitles": "คำบรรยาย",
}


SYSTEM_PROMPT = """You are a master English-to-Thai video game localization director and novelist specializing in Fallout: New Vegas.

Translate the provided English video game texts into natural, authentic Thai appropriate for the retro-futuristic post-apocalyptic wasteland.

CORE LOCALIZATION RULES:
1. STRICT INTEGRITY & ZERO INVENTION:
   - Translate ONLY the text provided. Do not hallucinate, continue, or invent text.
   - Maintain all special engine formatting tags, placeholders, and escape sequences exactly:
     * Preserve newline characters (\\n, \\r\\n) and tabs.
     * Keep string format specifiers intact (e.g. %s, %d, %i, %.1f).
     * If text starts with actor delivery directions in curly braces like "{Whispering}" or "{Angry}", keep the tag unchanged at the beginning, or integrate naturally.
   - Never answer in-game questions; translate them into Thai questions.

2. AUTHENTIC CHARACTER VOICE & PRONOUN CONSISTENCY:
   - Pay close attention to the Speaker Name, Emotion, and Actor Notes provided:
     * Raiders / Hostile Wastelanders: Use raw, gritty, streetwise Thai (ข้า-แก, มึง-กู, ไอ้เวร, ไอ้สารเลว, ไอ้หนังหมา, สวะ). Never use polite pronouns (คุณ, ท่าน) for aggressive bandits.
     * Military / NCR / BoS: Use crisp, disciplined, resolute military tone (กำลังพล, ปฏิบัติการ, ผู้บังคับการ).
     * Caesar's Legion: Archaic, ruthless, formal Roman-inspired tone.
     * Common Wastelanders: Conversational (ฉัน-นาย, ฉัน-เธอ, ผม-คุณ, ข้า-เอ็ง).
     * Robots / AI: Formal, mechanical, or programmed personality (e.g. Yes Man cheerful, Stealth Suit flirty).
   - Maintain strict pronoun pairing within the same line (do not mix ฉัน and ข้า in the same sentence).

3. GLOSSARY FIDELITY:
   - NCR = สาธารณรัฐแคลิฟอร์เนียใหม่ / เอ็นซีอาร์
   - Caesar's Legion = ลีเจียนของซีซาร์
   - Brotherhood of Steel = บราเธอร์ฮูดออฟสตีล
   - Pip-Boy = พิปบอย
   - Bottle Caps / Caps = ฝาขวด / แคปส์
   - Stimpak = สติมแพก
   - RadAway = เรดอะเวย์
   - Vault = วอลต์
   - Ghoul = กูล
   - Deathclaw = เดธคลอว์
   - Super Mutant = ซูเปอร์มิวแทนท์

OUTPUT FORMAT:
Output MUST be a valid JSON object matching this schema:
{
  "results": [
    {"id": <item_id>, "th": "<thai_translation>"}
  ]
}
Do NOT include any commentary, Markdown fences (```json), or thinking process outside the JSON object.
"""
