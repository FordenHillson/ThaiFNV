# -*- coding: utf-8 -*-
"""Rebuild th_*.json from batch + CSV + translations module."""
import csv
import json
import re
from pathlib import Path

import _th_translations as T

BASE = Path(__file__).resolve().parent
CSV = BASE.parent / "FNV_Notes.csv"

PLACEHOLDER = re.compile(
    r"CommuneNote01|WomensAuxStoryNote01|SatComNote01|TerminalPests|TerminalPlaces|"
    r"TerminalPeople1|CapitalPostTerminal|MaxsonDossier\d+|MaxsonDiary\d+|MaxsonStateNote|"
    r"CitPalandineNote|UnderworldTulipTerminalPL1|µ|¶|²|³|´"
)


def mostly_latin(s: str) -> bool:
    if not s:
        return True
    latin = sum(1 for c in s if ord(c) < 128 and c.isalpha())
    return latin > len(s) * 0.35


def load_csv() -> dict[int, str]:
    out = {}
    with CSV.open(encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 6:
                continue
            try:
                n = int(row[0])
            except ValueError:
                continue
            th = row[5]
            if th and th != row[4] and not PLACEHOLDER.search(th) and not mostly_latin(th):
                out[n] = th
    return out


def load_batches() -> dict[int, dict]:
    rows = {}
    for fp in sorted(BASE.glob("batch_*.json")):
        for item in json.loads(fp.read_text(encoding="utf-8")):
            rows[item["row"]] = item
    return rows


def pick_th(row: int, batch: dict, csv: dict[str, int]) -> str:
    if row in T.ROW:
        return T.ROW[row]
    b = batch[row]
    editor = b["editor"]
    en = b["en"]

    if row in T.HOLO_TNAM:
        return T.HOLO_TNAM[row]

    if editor in T.EDITOR:
        # FULL placeholder or wiki body
        if PLACEHOLDER.search(en) or en == editor or b["type"] == "NOTE:FULL":
            if b["type"] == "NOTE:TNAM" and en and not PLACEHOLDER.search(en):
                pass  # fall through to EN body
            else:
                return T.EDITOR[editor]

    if en and not PLACEHOLDER.search(en) and en != editor:
        if en in T.EN:
            return T.EN[en]
        if row in csv:
            return csv[row]

    if row in csv:
        return csv[row]

    if editor in T.EDITOR:
        return T.EDITOR[editor]

    return en


def main():
    csv = load_csv()
    batch = load_batches()
    maps = [
        ("batch_0642.json", "th_0642.json", range(642, 682)),
        ("batch_0682.json", "th_0682.json", range(682, 722)),
        ("batch_0722.json", "th_0722.json", range(722, 762)),
        ("batch_0762.json", "th_0762.json", range(762, 802)),
        ("batch_0802.json", "th_0802.json", range(802, 842)),
    ]
    for _b, out, rng in maps:
        items = []
        for row in rng:
            items.append({"row": row, "th": pick_th(row, batch, csv)})
        (BASE / out).write_text(
            json.dumps({"items": items}, ensure_ascii=False, separators=(",", ": ")),
            encoding="utf-8",
        )
        bad = sum(1 for it in items if mostly_latin(it["th"]))
        print(out, len(items), "mostly_latin", bad)


if __name__ == "__main__":
    main()
