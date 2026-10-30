# -*- coding: utf-8 -*-
"""Fill placeholder note rows with Thai adapted from Fallout wiki EN bodies."""
import json
import re
from pathlib import Path

WIKI = Path(
    r"C:\Users\saetanpee\.cursor\projects\d-backup-github-ThaiFNV\agent-tools\d1880349-6fb9-475b-aa55-158b94a0b994.txt"
)
BASE = Path(__file__).resolve().parent

# Gritty EN→TH pass (partial; keeps names/terms)
def grit(en: str) -> str:
    t = en
    reps = [
        ("I have to admit", "กูต้องยอmรับ"),
        ("I can't believe", "กูไmเชื่อ"),
        ("I finally", "ในที่สุdกู"),
        ("I killed a man", "กูฆ่aคnหnึg"),
        ("I tried again", "กูลองอีgครั้ง"),
        ("We're leaving", "เรaกำลังออก"),
        ("We declare ourselves", "เรaประกาศว่a"),
        ("What the hell", "เกิดอะไrวะ"),
        ("Fuck those grown-ups", "แม่งพวgผู้ใหญ่"),
        ("Fuck them all", "แม่งทuกคn"),
        ("Damn them all to Hell", "ใหgพวgมันไปนรก"),
        ("My God", "พระเจ้a"),
        ("Goddamn ", "ไอ้แม่ง "),
        (" psychotic son of a bitch", " ไอ้ psychotic ลูgแb"),
        ("Two-timing bitch", "ไอ้เหี้yสองหน้a"),
        ("the best damn ", "ที่ดีที่สุdแม่ง "),
        ("I don't know", "กูไmรu"),
        ("I just don't know", "กูไmรuจริgๆ"),
        ("Can we?", "ใช่ไหm?"),
        ("We're all okay.", "พวgเรaโอเค."),
        ("Alive, anyway.", "ยังมีชีviitอยู่."),
    ]
    for a, b in reps:
        t = t.replace(a, b)
    return t


def parse_wiki() -> dict[str, str]:
    text = WIKI.read_text(encoding="utf-8", errors="replace")
    out: dict[str, str] = {}
    for block in re.split(r"\n- Editor ID: ", text)[1:]:
        eid, _, rest = block.partition("\n")
        eid = eid.strip()
        chunk = re.split(r"\n- Base ID:", rest, maxsplit=1)[0]
        chunk = re.sub(r"^- Name:.*?\n", "", chunk, flags=re.M)
        body = chunk.strip()
        if body and not body.startswith("- "):
            out[eid] = body
    return out


def load_batches() -> dict[int, dict]:
    rows = {}
    for fp in sorted(BASE.glob("batch_*.json")):
        for item in json.loads(fp.read_text(encoding="utf-8")):
            rows[item["row"]] = item
    return rows


PLACEHOLDER = re.compile(
    r"TerminalPests|TerminalPlaces|TerminalPeople1|CapitalPostTerminal|"
    r"MaxsonDossier|MaxsonDiary|MaxsonState|CitPalandine|UnderworldTulip"
)


def main():
    wiki = parse_wiki()
    batch = load_batches()
    holo_tnam = {
        717: "LamplightHolo05",
        719: "LamplightHolo04",
        721: "LamplightHolo03",
        723: "LamplightHolo02",
        725: "LamplightHolo01",
    }
    holo_en = {
        "LamplightHolo05": (
            "We've been in here for 3 months now, and it's way better than it used to be. "
            "Who says kids can't take care of themselves? Jason has done a really good job keeping everyone busy. "
            "He says if we want to survive, we need to work together, and work hard. "
            "A few of the kids have started saying we're like a whole new city. A city of kids. "
            "They call it 'Little Lamplight.' It's so cool. All of us voted, in secret, and tomorrow "
            "we're going to tell Jason that he's the city's first mayor! He's going to be so happy with us."
        ),
        "LamplightHolo04": (
            "It's been almost two months, and we're all doing pretty good, even if we are all alone. "
            "There's a door that leads to a Vault, right here in the caverns. Every day we bang and bang, "
            "but they won't let us in. We can hear them in there! One time, a guy on the other side told us "
            "we were dead already. Fuck those grown-ups. Fuck them all. We don't need them ever again."
        ),
        "LamplightHolo03": (
            "Umm... I guess this thing is working. I'm Jason Grant. I'm ten years old. "
            "I'm in Ms. Delaney's class, Early Dawn Elementary. A month ago a big war came and everything was destroyed. "
            "Except us. We're still OK in these caves. Kinda. Ms. Delaney went out this morning to get help and she never came back, "
            "but the other adults never came back either. So now it's just us kids. A lot of the others still cry every day. "
            "They're really scared. I'm not. There's nothing to be scared of, as long as we don't go outside. "
            "Nobody else wants to be in charge, so I'm gonna try. Most of the kids listen to me already, so it should be easy."
        ),
        "LamplightHolo02": (
            "We're all okay. If you can call being stuck in a cave with 82 terrified kids okay. Alive, anyway. "
            "But I don't know what the hell we're going to do. It's been 4 days. Claudia went out this morning to look around, "
            "and never came back. Then Mr. Cob went out to look for her, and HE never came back either. "
            "So now there's only me, two other teachers, two of the parents who were chaperoning, and a few of the cavern staff. "
            "And all these poor kids. We've got enough food and water to last for awhile, I guess. But after that? "
            "I just don't know. We can't stay in here forever. Can we?"
        ),
        "LamplightHolo01": (
            "My name is Carrie Delaney. I teach fourth grade at the Early Dawn Elementary School, in Washington, D.C. "
            "Yesterday, October 23, 2077, half the school went on a field trip to Lamplight Caverns. "
            "We were packing up to leave when- when everything went crazy. The caves started shaking, the lights went out, "
            "the kids started screaming. My God... Mister Pollack went outside to see what was going on. "
            "When he came back in, he told us what he saw. Clouds. Mushroom clouds. It's finally happened. The end of the world."
        ),
    }

    for fn in ["th_0642.json", "th_0682.json", "th_0722.json", "th_0762.json", "th_0802.json"]:
        path = BASE / fn
        data = json.loads(path.read_text(encoding="utf-8"))
        n = 0
        for item in data["items"]:
            r = item["row"]
            th = item["th"]
            b = batch.get(r)
            if r in holo_tnam:
                tf = BASE / "_text" / f"row_{r}.txt"
                if tf.exists():
                    item["th"] = tf.read_text(encoding="utf-8").strip()
                else:
                    item["th"] = grit(holo_en[holo_tnam[r]])
                n += 1
                continue
            if not PLACEHOLDER.search(th):
                continue
            if not b:
                continue
            editor = b["editor"]
            if editor in wiki:
                item["th"] = grit(wiki[editor])
                n += 1
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ": ")),
            encoding="utf-8",
        )
        print(fn, "wiki_fill", n)


if __name__ == "__main__":
    main()
