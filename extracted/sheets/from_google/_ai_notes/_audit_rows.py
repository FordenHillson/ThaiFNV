# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path

base = Path(__file__).resolve().parent
rows = {}
for fp in sorted(base.glob("batch_*.json")):
    for it in json.loads(fp.read_text(encoding="utf-8")):
        rows[it["row"]] = it
PH = re.compile(
    r"CommuneNote01|WomensAuxStoryNote01|SatCom|TerminalPests|TerminalPlaces|"
    r"TerminalPeople1|CapitalPostTerminal|MaxsonDossier|MaxsonDiary\d+|MaxsonState|"
    r"CitPalandineNote|UnderworldTulipTerminalPL1|µ|¶|²|³|´"
)
for r in range(642, 842):
    it = rows[r]
    en = it["en"]
    tag = "PLACE" if (PH.search(en) or en == it["editor"]) else "BODY"
    print(r, tag, it["type"], it["editor"], en[:100].replace("\n", " "))
