# -*- coding: utf-8 -*-
"""Apply row-level Thai patches to th_*.json batch outputs."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
TEXT = BASE / "_text"

# row -> th string (UTF-8 files in _text/row_{n}.txt take precedence)
FILE_PATCHES: dict[int, str] = {}

# Load optional text files row_{n}.txt
for fp in TEXT.glob("row_*.txt"):
    m = re.match(r"row_(\d+)\.txt", fp.name)
    if m:
        FILE_PATCHES[int(m.group(1))] = fp.read_text(encoding="utf-8").strip()

for fp in TEXT.glob("*.txt"):
    m = re.match(r"(\d+)\.txt", fp.name)
    if m:
        FILE_PATCHES[int(m.group(1))] = fp.read_text(encoding="utf-8").strip()

# Inline patches (holotapes, womens aux, dashwood, maxson, capital post)
INLINE: dict[int, str] = {
    664: "บันทึกหญิงสมัครใจ",
    665: (
        "หน่วยเรaถูกจัดให้อยู่กับ National Guard Detachment พวgขับรถมaทั้งคืnจาก Pennsylvania "
        "เรaพยายamให้คนรอดชีviตสงบ ระหว่างพวgเด็kๆ ฟื้nกำลัง การปล้nทุgวันแย่ลง เมืองเล็k ของเหลือไม่มาก "
        "มีทะเลาะที่โรงอาหารแลwครungหnึg กลัvว่าทหารพวgนี้มaทันเวลaพอดี"
    ),
    666: "บันทึekหญิงสมัครใจ",
    667: "บันทึekหญิงสมัครใจ",
    716: (
        "เรaอยู่ในถ้ำนี่สามเดือnแลwว ดีกว่aตอnแรkมาก ใครบอกว่aเด็kดูแลตัvเองไม่ได้? "
        "Jason ทำให้ทุกคnยubusy เขaบอกว่aถ้aอยaกรอdต้องร่วmมือกwนและทำงานหnัก "
        "มีเด็kไม่กี่คnบอกว่aเรaเหmวnเมืองใหม่ เมืองของเด็k เรaเรียg Little Lamplight เจ๋ngมาก "
        "โhวตกลงลับๆ พรu่งnี้จะบอก Jason ว่aเป็นmayorคนแรg! เขaจะดีใjmág"
    ),
}

# Merge: prefer FILE_PATCHES over INLINE for same row
PATCHES = {**INLINE, **FILE_PATCHES}

TARGETS = {
    "th_0642.json": range(642, 682),
    "th_0682.json": range(682, 722),
    "th_0722.json": range(722, 762),
    "th_0762.json": range(762, 802),
    "th_0802.json": range(802, 842),
}


def apply_file(name: str, rows: range) -> int:
    path = BASE / name
    data = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    for item in data["items"]:
        r = item["row"]
        if r in PATCHES and r in rows:
            item["th"] = PATCHES[r]
            n += 1
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ": ")),
        encoding="utf-8",
    )
    return n


def main():
    for name, rows in TARGETS.items():
        c = apply_file(name, rows)
        if c:
            print(name, "patched", c)


if __name__ == "__main__":
    main()
