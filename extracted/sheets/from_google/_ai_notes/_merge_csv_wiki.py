# -*- coding: utf-8 -*-
import csv
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
CSV = BASE.parent / "FNV_Notes.csv"

PLACEHOLDER = re.compile(
    r"TerminalPests|TerminalPlaces|TerminalPeople1|CapitalPostTerminal|"
    r"MaxsonDossier|MaxsonDiary|MaxsonState|CitPalandine|µ|¶|²|³|´"
)


def mostly_latin(s: str) -> bool:
    if not s:
        return False
    latin = sum(1 for c in s if ord(c) < 128 and c.isalpha())
    return latin > len(s) * 0.35


def load_csv_th() -> dict[int, str]:
    out = {}
    with CSV.open(encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 6:
                continue
            try:
                n = int(row[0])
            except ValueError:
                continue
            th, en = row[5], row[4]
            if not th or th == en or PLACEHOLDER.search(th):
                continue
            if mostly_latin(th):
                continue
            out[n] = th
    return out


def load_holo_rows():
    fixes = {
        716: "26 มกราคม 2077 -- Little Lamplight!",
        718: "ไดอารี่ของ Jason Grant -- บันทึกที่ 2",
        720: "ไดอารี่ของ Jason Grant -- บันทึกที่ 1",
        722: "บันทึekของ Carrie Delaney บันทึekที่ 2",
        724: "บันทึekของ Carrie Delaney บันทึekที่ 1",
    }
    text = BASE / "_text"
    for r in (717, 719, 721, 723, 725):
        fp = text / f"row_{r}.txt"
        if fp.exists():
            fixes[r] = fp.read_text(encoding="utf-8").strip()
    carrie2 = text / "carrie2_ok.txt"
    if carrie2.exists():
        fixes[723] = carrie2.read_text(encoding="utf-8").strip()
    return fixes


def main():
    csv_th = load_csv_th()
    holo = load_holo_rows()
    for fn in ["th_0642.json", "th_0682.json", "th_0722.json", "th_0762.json", "th_0802.json"]:
        path = BASE / fn
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data["items"]:
            r = item["row"]
            if r in holo:
                item["th"] = holo[r]
            elif r in csv_th and (mostly_latin(item["th"]) or PLACEHOLDER.search(item["th"])):
                item["th"] = csv_th[r]
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ": ")),
            encoding="utf-8",
        )
        print(fn, "merged")


if __name__ == "__main__":
    main()
