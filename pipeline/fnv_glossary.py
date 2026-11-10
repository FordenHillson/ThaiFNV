#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fnv_glossary.py — คลังศัพท์มาตรฐาน โทนผู้พูด และแนวทางแปลสำหรับ Fallout: New Vegas (ThaiFNV)

นโยบายที่ล็อก:
- ชื่อเฉพาะใช้ทับศัพท์ไทยรูปเดียว (ไม่คง EN)
- โทนสรรพนามยึดบทบาทผู้พูด + Emotion / ActorNotes
"""

from __future__ import annotations

import re
from typing import Any

# คำศัพท์เฉพาะและชื่อเฉพาะที่ต้องคงเส้นคงวา (รูปเดียว — ไม่ใช้ "A / B")
FNV_TERMS: dict[str, str] = {
    # Factions & Groups
    "New California Republic": "สาธารณรัฐแคลิฟอร์เนียใหม่",
    "NCR": "เอ็นซีอาร์",
    "Caesar's Legion": "ลีเจียนของซีซาร์",
    "Caesar": "ซีซาร์",
    "The Legion": "เดอะลีเจียน",
    "Legion": "ลีเจียน",
    "Brotherhood of Steel": "บราเธอร์ฮูดออฟสตีล",
    "Great Khans": "เกรตคานส์",
    "Boomers": "บูมเมอร์ส",
    "Powder Gangers": "พาวเดอร์แกงเกอร์ส",
    "Fiends": "ฟีนด์ส",
    "Followers of the Apocalypse": "ผู้ติดตามแห่งวันสิ้นโลก",
    "Followers": "ผู้ติดตาม",
    "Enclave": "เอนเคลฟ",
    "Chairmen": "แชร์แมน",
    "Omertas": "โอเมอร์ทา",
    "White Glove Society": "สมาคมถุงมือขาว",
    "Gun Runners": "กันรันเนอร์ส",
    "Crimson Caravan": "คริมสันคาราวาน",
    "Kings": "เดอะคิงส์",

    # Major Characters & Titles
    "Courier": "เดอะคูเรียร์",
    "The Courier": "เดอะคูเรียร์",
    "Mr. House": "มิสเตอร์เฮาส์",
    "Yes Man": "เยสแมน",
    "Legate Lanius": "เลเกต ลานิอุส",
    "Lanius": "ลานิอุส",
    "Father Elijah": "ฟาเธอร์ เอไลจาห์",
    "Elijah": "เอไลจาห์",
    "Joshua Graham": "โจชัว เกรแฮม",
    "Burned Man": "ชายผู้ถูกเผา",
    "Ulysses": "ยูลิสซิส",
    "Doc Mitchell": "ด็อก มิตเชลล์",
    "Doctor Usanagi": "ด็อกเตอร์ อูซานากิ",
    "Doctor Henry": "ด็อกเตอร์ เฮนรี",
    "Sunny Smiles": "ซันนี่ สไมล์ส",
    "Craig Boone": "เครก บูน",
    "Boone": "บูน",
    "Veronica": "เวโรนิกา",
    "Raul": "ราอูล",
    "Arcade Gannon": "อาร์เคด แคนนอน",
    "Arcade": "อาร์เคด",
    "Rose of Sharon Cassidy": "แคสส์",
    "Cass": "แคสส์",
    "Cassidy": "แคสส์",
    "Lily": "ลิลี่",
    "Benny": "เบนนี่",
    "Swank": "สวองค์",
    "ED-E": "อีดี-อี",
    "Rex": "เร็กซ์",
    "Victor": "วิกเตอร์",
    "Joe Cobb": "โจ คอบบ์",
    "Jason Bright": "เจสัน ไบรท์",

    # Key Locations
    "Mojave Wasteland": "แดนรกร้างโมฮาวี",
    "Mojave": "โมฮาวี",
    "Wasteland": "แดนรกร้าง",
    "New Vegas": "นิวเวกัส",
    "Vegas": "เวกัส",
    "The Strip": "เดอะสตริป",
    "Strip": "สตริป",
    "Freeside": "ฟรีไซด์",
    "Westside": "เวสต์ไซด์",
    "Goodsprings": "กู๊ดสปริงส์",
    "Novac": "โนแวค",
    "Primm": "พริมม์",
    "Boulder City": "โบลเดอร์ซิตี",
    "Hoover Dam": "เขื่อนฮูเวอร์",
    "Lucky 38": "ลัคกี้ 38",
    "Sierra Madre": "เซียร่า มาเดร",
    "Zion Canyon": "หุบเขาไซออน",
    "Zion": "ไซออน",
    "Big MT": "บิ๊กเอ็มที",
    "Big Mountain": "บิ๊กเมาน์เทน",
    "The Divide": "เดอะดีไวด์",
    "Camp McCarran": "แคมป์แมคแคร์แรน",
    "McCarran": "แมคแคร์แรน",
    "Nellis Air Force Base": "ฐานทัพอากาศเนลลิส",
    "Nellis": "เนลลิส",
    "REPCONN": "เรปคอน",
    "Fortification Hill": "ฟอร์ทิฟิเคชันฮิลล์",
    "The Fort": "เดอะฟอร์ท",

    # Items & Gameplay Concepts
    "Vault": "วอลต์",
    "Vault-Tec": "วอลต์-เทค",
    "Pip-Boy": "พิปบอย",
    "Caps": "แคปส์",
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
    "Trooper": "ทหาร",
    "Ranger": "เรนเจอร์",
    "Settler": "ผู้อพยพ",
    "Merchant": "พ่อค้า",
    "Guard": "ยาม",
    "Doctor": "หมอ",
    "Terminal": "เทอร์มินัล",

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
    "Radroach": "เรดโรช",
    "Securitron": "ซีเคียวริตรอน",
    "Lobotomite": "โลโบโทไมท์",

    # S.P.E.C.I.A.L. & Skills (ไทยล้วน — ไม่ใส่วงเล็บ EN)
    "Strength": "พละกำลัง",
    "Perception": "การรับรู้",
    "Endurance": "ความทรหด",
    "Charisma": "เสน่ห์",
    "Intelligence": "สติปัญญา",
    "Agility": "ความคล่องตัว",
    "Luck": "โชค",
    "Barter": "การค้าขาย",
    "Energy Weapons": "อาวุธพลังงาน",
    "Explosives": "วัตถุระเบิด",
    "Guns": "อาวุธปืน",
    "Lockpick": "การสะเดาะกลอน",
    "Medicine": "การแพทย์",
    "Melee Weapons": "อาวุธระยะประชิด",
    "Repair": "การซ่อมแซม",
    "Science": "วิทยาศาสตร์",
    "Sneak": "การลอบเร้น",
    "Speech": "การเจรจา",
    "Survival": "การเอาชีวิตรอด",
    "Unarmed": "มือเปล่า",

    # UI & Controls
    "Continue": "เล่นต่อ",
    "New": "เริ่มเกมใหม่",
    "Load": "โหลดเซฟ",
    "Save": "บันทึกเกม",
    "Settings": "การตั้งค่า",
    "Credits": "เครดิต",
    "Downloadable Content": "เนื้อหาดาวน์โหลด",
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


# ---------------------------------------------------------------------------
# Speaker register — บทบาท → คู่สรรพนาม + กฎโทน
# ---------------------------------------------------------------------------

SPEAKER_REGISTER: dict[str, dict[str, Any]] = {
    "doctor": {
        "label": "แพทย์ / บุคลากรการแพทย์",
        "pronouns": "ผม–คุณ (ชาย) หรือ ฉัน–คุณ (หญิง)",
        "hint": "register: doctor → ผม/คุณ หรือ ฉัน/คุณ — สุภาพ เป็นมืออาชีพ — ห้าม แก/มึง/กู",
        "forbid_rude": True,
        "forbid_tokens": ("แก", "มึง", "กู"),
    },
    "military": {
        "label": "ทหาร NCR / Brotherhood",
        "pronouns": "ผม–คุณ",
        "hint": "register: military → ผม/คุณ — โทนวินัย คำสั่งการ ชัดเจน",
        "forbid_rude": True,
        "forbid_tokens": ("มึง", "กู"),
    },
    "legion": {
        "label": "Caesar's Legion",
        "pronouns": "ข้า–ท่าน",
        "hint": "register: legion → ข้า/ท่าน — โทนโบราณ เข้มงวด โหดเหี้ยม",
        "forbid_rude": False,
        "forbid_tokens": (),
    },
    "raider": {
        "label": "ราเดอร์ / Fiends / Powder Gangers / ศัตรู",
        "pronouns": "กู–มึง",
        "hint": "register: raider → กู/มึง — หยาบ ก้าวร้าว ห้าม คุณ/ท่าน ในบทปกติ",
        "forbid_rude": False,
        "forbid_tokens": (),
    },
    "civilian": {
        "label": "ชาวเมือง / ชาวแดนรกร้างทั่วไป",
        "pronouns": "ฉัน–นาย หรือ ผม–คุณ",
        "hint": "register: civilian → ฉัน/นาย หรือ ผม/คุณ ตามเพศและอายุ — สนทนาเป็นธรรมชาติ",
        "forbid_rude": False,
        "forbid_tokens": (),
    },
    "robot": {
        "label": "หุ่น / AI",
        "pronouns": "ฉัน–คุณ หรือโทนโปรแกรม",
        "hint": "register: robot → โทนกลไก/โปรแกรม — ไม่ใช้คำหยาบชาวบ้าน (ห้าม กู/มึง)",
        "forbid_rude": True,
        "forbid_tokens": ("แก", "มึง", "กู"),
    },
    "default": {
        "label": "ไม่ทราบบทบาท",
        "pronouns": "ผม–คุณ หรือ ฉัน–นาย",
        "hint": "register: default → ใช้โทนสุภาพปานกลาง ผม/คุณ หรือ ฉัน/นาย — อ่าน Emotion/ActorNotes ก่อน",
        "forbid_rude": False,
        "forbid_tokens": (),
    },
}

# จับคู่ชื่อผู้พูด / คำใบ้ → บทบาท
_REGISTER_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "doctor",
        re.compile(
            r"\b(doc(?:tor)?\.?\s+\w+|dr\.?\s+\w+|usanagi|mitchell|sawbones|"
            r"follow(?:ers)?.*(?:doctor|medic)|doctormedical|auto-?doc)\b",
            re.I,
        ),
    ),
    (
        "military",
        re.compile(
            r"\b(ncr|trooper|ranger|commander|captain|lieutenant|sergeant|"
            r"brotherhood|paladin|knight|scribe|elder|colonel|general)\b",
            re.I,
        ),
    ),
    (
        "legion",
        re.compile(
            r"\b(legion|legate|centurion|decanus|frumentarii|caesar|lanius|vulpes)\b",
            re.I,
        ),
    ),
    (
        "raider",
        re.compile(
            r"\b(raider|fiend|powder\s*ganger|cobb|viper|jackal|thug|bandit|"
            r"convict|escaped\s*convict)\b",
            re.I,
        ),
    ),
    (
        "robot",
        re.compile(
            r"\b(yes\s*man|securitron|victor|ed-?e|protectron|mister\s*handy|"
            r"auto-?doc|robot|mr\.\s*house|house)\b",
            re.I,
        ),
    ),
]


def resolve_register(
    speaker: str = "",
    emotion: str = "",
    actor_notes: str = "",
    category: str = "",
    context_hint: str = "",
) -> dict[str, Any]:
    """เลือกบทบาทโทนจากชื่อผู้พูดและบริบท — คืน dict จาก SPEAKER_REGISTER พร้อม key."""
    blob = " ".join(
        x for x in (speaker, emotion, actor_notes, category, context_hint) if x
    ).strip()
    role = "default"
    if blob:
        for role_name, pat in _REGISTER_RULES:
            if pat.search(blob):
                role = role_name
                break
        else:
            # ชื่อขึ้นต้น Doc / Doctor
            if re.match(r"^\s*(doc(?:tor)?|dr)\b", speaker or "", re.I):
                role = "doctor"
            elif re.search(r"DoctorMedical", blob, re.I):
                role = "doctor"

    info = dict(SPEAKER_REGISTER[role])
    info["key"] = role

    # Emotion / ActorNotes ปรับความเข้มได้ แต่หมอ/หุ่น/ทหารยังห้ามกระโดดไป มึง
    emo = f"{emotion} {actor_notes}".lower()
    if role == "doctor" and any(w in emo for w in ("angry", "shout", "furious")):
        info["hint"] = (
            info["hint"]
            + " | emotion เข้มขึ้นได้ แต่ยังสุภาพมืออาชีพ — ห้าม แก/มึง/กู"
        )
    return info


def match_glossary_terms(texts: list[str]) -> dict[str, str]:
    """ดึงเฉพาะศัพท์จาก FNV_TERMS ที่ปรากฏในข้อความของ batch (ยาวก่อนสั้น).

    หลีกเลี่ยง false positive เช่น "New" ใน "New Vegas" หรือ "Luck" ใน "Lucky 38"
    โดยใช้ขอบคำ และไม่นับคีย์ที่ซ้อนในคีย์ที่ match แล้ว
    """
    blob = "\n".join(texts)
    if not blob:
        return {}
    hits: dict[str, str] = {}
    matched_spans: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        for a, b in matched_spans:
            if start < b and end > a:
                return True
        return False

    for en in sorted(FNV_TERMS.keys(), key=len, reverse=True):
        # คำสั้นมากที่เป็น UI ทั่วไป — จับเฉพาะ exact ทั้งสตริงรายบรรทัด
        if en in {"New", "Load", "Save", "Quit", "Luck", "Guns", "Jet"}:
            for line in blob.splitlines():
                if line.strip() == en:
                    hits[en] = FNV_TERMS[en]
            continue

        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(en)}(?![A-Za-z0-9])")
        for m in pattern.finditer(blob):
            if overlaps(m.start(), m.end()):
                continue
            hits[en] = FNV_TERMS[en]
            matched_spans.append((m.start(), m.end()))
            break
    return hits


def format_glossary_block(terms: dict[str, str]) -> str:
    if not terms:
        return "(no glossary hits in this batch)"
    lines = [f"- {en} = {th}" for en, th in sorted(terms.items(), key=lambda x: -len(x[0]))]
    return "\n".join(lines)


_PRONOUN_FIRST = ("ฉัน", "ผม", "ข้า", "กู", "ดิฉัน", "เรา")
_PRONOUN_SECOND = ("คุณ", "นาย", "เธอ", "ท่าน", "เอ็ง", "มึง", "แก")
_CORRUPTION_RE = re.compile(r"[\u0e00-\u0e7f]ek[\u0e00-\u0e7f]|บันทึek")
_THAI_CHAR = r"\u0e00-\u0e7f"


def _has_thai_token(text: str, tok: str) -> bool:
    """จับสรรพนามแบบขอบคำ — ไม่สะกิดทับศัพท์เช่น กู๊ดสปริงส์ / พาวเดอร์แกงเกอร์ส."""
    if not tok:
        return False
    return (
        re.search(rf"(?<![{_THAI_CHAR}]){re.escape(tok)}(?![{_THAI_CHAR}])", text)
        is not None
    )


def qa_check_translation(
    th: str,
    en: str = "",
    register_key: str = "default",
) -> list[str]:
    """คืนรายการเหตุผลที่ fail — ว่าง = ผ่าน."""
    fails: list[str] = []
    text = (th or "").strip()
    if not text:
        fails.append("empty")
        return fails

    if text.startswith("{") and '"results"' in text:
        fails.append("json_leak")
    if "```" in text:
        fails.append("markdown_fence")
    if _CORRUPTION_RE.search(text):
        fails.append("corruption")

    # สรรพนามปนคู่ที่หนึ่งในบรรทัดเดียว
    first_hits = [p for p in _PRONOUN_FIRST if _has_thai_token(text, p)]
    if len(set(first_hits)) >= 2:
        fails.append("pronoun_mix_first")
    # มึง+คุณ หรือ กู+คุณ ในบรรทัดเดียวมักผิดโทน
    if (
        _has_thai_token(text, "มึง") or _has_thai_token(text, "กู")
    ) and (
        _has_thai_token(text, "คุณ") or _has_thai_token(text, "ท่าน")
    ):
        fails.append("pronoun_mix_register")

    reg = SPEAKER_REGISTER.get(register_key) or SPEAKER_REGISTER["default"]
    for tok in reg.get("forbid_tokens") or ():
        if _has_thai_token(text, tok):
            fails.append(f"register_forbid:{tok}")

    # ความยาวผิดปกติมาก
    if en and len(en) > 20 and len(text) > len(en) * 3:
        fails.append("too_long")

    return fails


SYSTEM_PROMPT = """You are a master English-to-Thai video game localization director specializing in Fallout: New Vegas.

Translate English game text into natural Thai for the retro-futuristic post-apocalyptic Mojave.

CORE LOCALIZATION RULES:
1. STRICT INTEGRITY & ZERO INVENTION:
   - Translate ONLY the provided 'en' text. Do not invent, continue, or answer in-game questions.
   - Preserve engine tags and placeholders exactly: \\n, \\r\\n, %s, %d, %i, %.1f, and curly delivery tags like {Whispering} or {Angry} at the start when present.
   - Never output Markdown fences or commentary outside the JSON object.

2. PROPER NOUNS = THAI TRANSLITERATION (single locked form):
   - Do NOT leave major names/factions/places in English.
   - Use the batch glossary block when provided. Key examples:
     NCR = เอ็นซีอาร์ | Caesar's Legion = ลีเจียนของซีซาร์ | Brotherhood of Steel = บราเธอร์ฮูดออฟสตีล
     Goodsprings = กู๊ดสปริงส์ | New Vegas = นิวเวกัส | Pip-Boy = พิปบอย | Vault = วอลต์
     Courier = เดอะคูเรียร์ | Stimpak = สติมแพก | Caps = แคปส์ | Ghoul = กูล | Deathclaw = เดธคลอว์
   - Exception: keep pure engine codes / format tokens / V.A.T.S. as-is.

3. SPEAKER REGISTER (mandatory — read speaker, emotion, actor_notes, quest/topic, and the item's 'register' hint BEFORE choosing pronouns):
   - doctor / medical (Doc Mitchell, Doctor Usanagi, Doctor*, Followers medics): ผม–คุณ or ฉัน–คุณ. Professional, polite. NEVER แก / มึง / กู.
   - military (NCR, Brotherhood): ผม–คุณ, crisp disciplined tone.
   - legion: ข้า–ท่าน, archaic ruthless Roman-inspired tone.
   - raider / Fiends / Powder Gangers / hostiles: กู–มึง when aggressive; never polite คุณ/ท่าน for bandits.
   - civilian: ฉัน–นาย or ผม–คุณ by gender/age.
   - robot / AI (Yes Man, Securitron, Auto-Doc): mechanical/programmed; never street slang กู/มึง.
   - Emotion/ActorNotes may intensify tone but must NOT override doctor/military/robot bans on แก/มึง/กู.
   - One pronoun pair per line — never mix ฉัน with ข้า, or กู with คุณ, in the same sentence.

4. OUTPUT FORMAT:
Return ONLY valid JSON:
{"results": [{"id": <item_id>, "th": "<thai_translation>"}]}
"""
