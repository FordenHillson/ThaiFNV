# -*- coding: utf-8 -*-
"""Fill remaining Dashwood / Capital Post / Maxson rows from wiki dump + manual Thai."""
import json
import re
from pathlib import Path

WIKI = Path(
    r"C:\Users\saetanpee\.cursor\projects\d-backup-github-ThaiFNV\agent-tools\d1880349-6fb9-475b-aa55-158b94a0b994.txt"
)
BASE = Path(__file__).resolve().parent

# Manual Thai (wiki EN matched by editor id in batch)
TH_BY_EDITOR = {
    "DashwoodTerminalPests5": (
        "กูต้องยอmรับ สนใj Robobrains มaตลอd — หุ่nยyndrives ใชaสmoong แลwเสียngสาวเซeksy "
        "กูสงสัy สmoongคnจริgหรือแค่บันทึk โดn mind blast ครungหnึg ปวdหัvสามวu"
    ),
    "DashwoodTerminalPests4": (
        "หมีnใน Capital Wasteland แบbนีe — ไม่มีบอลยางให้เล่n แต่กรงเล็bโหด กรงเล็bฟัน นิสัยแยg"
    ),
    "DashwoodTerminalPests3": (
        "Radscorpions มีทุgที่กูไป — ข่าวลือว่aมaจาก Emperor Scorpion ตอnก่อnสงคราม อธิบายได้ว่aทำไmเยอdขนาดนีe"
    ),
    "DashwoodTerminalPests2": (
        "Ghoul บ้a — สmoongเน่aจนไม่รuเรื่อง Argyle กับกูสู้พวgนีeไม่รuกี่ครั้ง ทeนเขaชอbฆ่aเหmือnแกgตัvเอง"
    ),
    "DashwoodTerminalPests1": (
        "ปูเดิnโคตรแม่ง — ฆ่aยาก แต่กิnอร่อy เปลือgแข็g แต่หน้aไม่เกราะ (โชคดี Argyle หมuยขวaแรg)"
    ),
    "DashwoodTerminalPlaces5": (
        "เมืองรอบระเบิดที่ยังไม่ทำงan — Megaton สไตล์กูเลย สมัyก่อnยugกว่a ไปดืmหรือหaสาวได้ดw Moriarty มีร้anตัvเองแลw ไม่แปลg"
    ),
    "DashwoodTerminalPlaces4": (
        "เมืองคnตาย — หรือไม่ตายกbแลw อยู่ใตgพิพิธภัณฑgประวัตiศาสตrอเมริk Argyle กับกูไปบ่อy กูเคยได้เป็น 'Ghoul กิตติมศักดิ์' ปี '51 ควรกลับไปเยี่ยm"
    ),
    "DashwoodTerminalPlaces2": (
        "เมืองใตgดิn — King Crag เอaแคgเกิnไป Argyle กับกูพal slaver ไปทำใหgที่นัnพัง ผิดพลาดจริgๆ"
    ),
    "DashwoodTerminalPlaces1": (
        "ถังขยะอันตรายสุdใน Capital Wasteland ขายทุgอย่างที่มีชีvit สมัyก่อn Harmon Jurley หัvหน้a psychotic ลือกิn slave ที่ขายไม่ได้"
    ),
    "DashwoodTerminalPeople4": (
        "คนรับใช้ที่ดีที่สุd — แกr ซuksal กลิ่nเหมaนถuงเน่a ครั้งสุdท้ายเจo Argyle ที่ Rockopolis หลายทศวรรษก่อn ยังอยู่ข้างนอกสักที่"
    ),
    "DashwoodTerminalPeople3": (
        "Destiny ที่รัก — เจ้aของ Blue Destiny Brothel สาวสวยที่สุdที่เคยได้สัมผัs ตายอหิวเสาะฤดูร้อน '49 (เลยปิดซ่องตลอdกาล)"
    ),
    "DashwoodTerminalPeople1": (
        "Craggy ราชa Rockopolis ใหgที่พัก Argyle กับกูฤดูร้อน '48 มีเรื่องลูgสาวเลยไล่ออก "
        "กลับไปอีgทีไม่กี่ปี แตgพa slaver เขaไม่พอใj — ครั้งสุdท้ายที่เห็n Argyle หลังเขaช่วgชีvitครั้งที่ร้อย"
    ),
    "CapitalPostTerminalNote3a": (
        "โดย Dorothy Proud ผู้สื่อข่าว Capital Post — สหประชาชatิยุbเมื่อวanนีe ยุคสงบสuขจบลง "
        "Okiri กล่าวว่a 'วanนนีeเป็นวanที่เศรsสำหrbcสหรัฐฯ แต่โลgเศรsกว่a' ทุgชnatioจะยgายออกภายในสัปdหa"
    ),
    "CapitalPostTerminalNote2b": (
        "โดย Walter \"Street Beat\" Munroe — กองทัพยืนยันกำลังพัฒนaอาวุธซูเปอrเพื่อปลdปล่อy Anchorage "
        "Chase บอก 'ถึgเวลaเปิดไพ่ทุgใบใหgจีnเห็n' แต่ยังไม่บอกรายละเอียdอาวุธ"
    ),
    "CapitalPostTerminalNote1b": (
        "โดย Walter Munroe — ความอดทนต่อจลatจลอาหารถึgขีดจำกัด Eccleston บอกใหgคnต่อแถว กิn แลwกลับบ้an "
        "'เรaเป็นคนอเมริk!'"
    ),
    "CapitalPostTerminalNote2a": (
        "โดย Dorothy Proud — สหรัฐฯ ประกาศ annex แคนadา ทันที หลังเกือb sabotage pipeline ใน Alaska "
        "Babcock: 'Little America เป็นของเรa — จริgๆ กbมaเป็นมaตลอd'"
    ),
    "CapitalPostTerminalNote1a": (
        "โดย Dorothy Proud — กองทัพสหรัฐฯ ปลdปล่อy Anchorage หลังยgดครองจีnกว่aสิบปี "
        "'land of the free' กลับมaอีgครั้ง"
    ),
    "MaxsonDossier4": (
        "เกิด 2267 — ลูgสุdท้ายของ Jonathan กับ Jessica Maxson ส่งไป Citadel ใหg Elder Lyons เลี้ยg "
        "เพราะความไม่แน่นอนใน Western Brotherhood ตอnนีeยังอยู่ Citadel ไม่มีกำหนด"
    ),
    "MaxsonDossier3": (
        "เกิด 2097 — ลูg John Maxson II เป็น Paladin 2135 ขึn High Elder 2155 หลังพ่อตายกับ Vipers "
        "2162 เกี่ยvข้องกับ 'Vault Dweller' ตอnอายu 65"
    ),
    "MaxsonDossier2": (
        "High Elder 2135–2155 ลูg Roger Maxson ตาย 2155 จากลูgศรพoison Vipers ตอnไม่ใส่หmuวก"
    ),
    "MaxsonDossier1": (
        "รองหัvหน้a security West Tek ยgาย Mariposa รับช่วงหลัง Spindel breakdown ประหardนักวิทยาศาสตr "
        "เห็n FEV แลwทิ้gกองทัพ ก่อตั้ง Brotherhood ที่ Lost Hills High Elder คnแรg"
    ),
    "MaxsonStateNote": (
        "รัฐ Maxson ใน New California Republic ตั้งใกลg Lost Hills Bunker อยู่ภายใตgการคุmครอง Brotherhood "
        "ไม่มีข้อมูลเพิ่mเตim"
    ),
    "CitPalandineNote": (
        "UFO รหัส 'Palandine' ตก Hagerstown 3 พ.ค. 2062 เก็bกลับไม่ได้ อาจมี stealth หรือซ่อmแลwออกไป "
        "ยืนยันแลw — เรaไม่ได้อยู่คnเดียv"
    ),
    "MaxsonDiary11": (
        "วanนนีeเรaออกจากที่แม่งนีe กูนำทาง exodus ไป bunker รัฐบาลที่ Lost Hills ทิ้g log ไว้ใหgฝังเมื่อที่นี่โดนแลกเปลี่ยn"
    ),
    "MaxsonDiary10": (
        "กูโนmใหgฝังนักวิทยาศาสตr ไม่รuทำไm อาจลดความรuสึkผิด ตอnคnสุdท้ายกำลgจะตาย กูเริ่mเชื่อเรื่oราวของพวgเขa พระเจ้a กูกลายเป็นอะไr"
    ),
    "MaxsonDiary8": (
        "ไมgเชื่อพวg bastard ทำจริg ใหg A-bomb บิn ตอnไล่ von Felden สัญญาณขad ศูนย์วิจัยน่aโดnแรg "
        "เรaไม่น่aโดน แตgจีnคงมaทัน โชคดียgายครอบครัvเขa base เมื่อวanก่อn ยังไม่รu fallout"
    ),
    "MaxsonDiary6": (
        "กูตอbวิทยุออกไป ไม่รuทำไmไม่มีใครมaดูตอnเรaหยุdตอb ประกาศ secede แลw Jefferson Davis ประวัตiศาสตrจะว่aกูยังไง"
    ),
    "MaxsonDiary5": (
        "ฆ่a Anderson แลwกูเป็นหัvหน้aชัด สอบปากคำจบด้วยการยิง Shellman อ้างคำสั่งเฉพาะเจาะจงเกิnไป รuสึkแยgในท้องว่aจบยังไง"
    ),
}


def parse_wiki_editors() -> dict[str, str]:
    text = WIKI.read_text(encoding="utf-8", errors="replace")
    editors: dict[str, str] = {}
    blocks = re.split(r"\n- Editor ID: ", text)
    for block in blocks[1:]:
        first_line, _, rest = block.partition("\n")
        eid = first_line.strip()
        body = rest.strip()
        body = re.sub(r"\n- Base ID:.*", "", body, flags=re.S).strip()
        if body:
            editors[eid] = body
    return editors


def load_batches() -> dict[int, dict]:
    rows = {}
    for fp in sorted(BASE.glob("batch_*.json")):
        for item in json.loads(fp.read_text(encoding="utf-8")):
            rows[item["row"]] = item
    return rows


def main():
    wiki = parse_wiki_editors()
    batch = load_batches()
    targets = [
        ("th_0722.json", 722, 762),
        ("th_0762.json", 762, 802),
        ("th_0802.json", 802, 842),
    ]
    for fn, lo, hi in targets:
        path = BASE / fn
        data = json.loads(path.read_text(encoding="utf-8"))
        n = 0
        for item in data["items"]:
            r = item["row"]
            if not (lo <= r < hi):
                continue
            b = batch.get(r)
            if not b:
                continue
            editor = b["editor"]
            th = item["th"]
            if re.search(
                r"TerminalPests|TerminalPlaces|TerminalPeople1|CapitalPostTerminal|MaxsonDossier|MaxsonDiary|MaxsonState|CitPalandine",
                th,
            ):
                if editor in TH_BY_EDITOR:
                    item["th"] = TH_BY_EDITOR[editor]
                    n += 1
                elif editor in wiki and b["type"] == "NOTE:TNAM":
                    # fallback: keep English wiki body flagged — skip
                    pass
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ": ")),
            encoding="utf-8",
        )
        print(fn, "filled", n)


if __name__ == "__main__":
    main()
