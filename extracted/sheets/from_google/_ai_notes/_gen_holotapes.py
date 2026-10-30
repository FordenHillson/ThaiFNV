# -*- coding: utf-8 -*-
from deep_translator import GoogleTranslator
import json
from pathlib import Path

t = GoogleTranslator(source="en", target="th")
texts = {
    716: (
        "We've been in here for 3 months now, and it's way better than it used to be. "
        "Who says kids can't take care of themselves? Jason has done a really good job keeping everyone busy. "
        "He says if we want to survive, we need to work together, and work hard. "
        "A few of the kids have started saying we're like a whole new city. A city of kids. "
        "They call it 'Little Lamplight.' It's so cool. All of us voted, in secret, and tomorrow "
        "we're going to tell Jason that he's the city's first mayor! He's going to be so happy with us."
    ),
    719: (
        "It's been almost two months, and we're all doing pretty good, even if we are all alone. "
        "There's a door that leads to a Vault, right here in the caverns. Every day we bang and bang, "
        "but they won't let us in. We can hear them in there! One time, a guy on the other side told us "
        "we were dead already. Fuck those grown-ups. Fuck them all. We don't need them ever again."
    ),
    721: (
        "Umm... I guess this thing is working. I'm Jason Grant. I'm ten years old. "
        "I'm in Ms. Delaney's class, Early Dawn Elementary. A month ago a big war came and everything was destroyed. "
        "Except us. We're still OK in these caves. Kinda. Ms. Delaney went out this morning to get help and she never came back, "
        "but the other adults never came back either. So now it's just us kids. A lot of the others still cry every day. "
        "They're really scared. I'm not. There's nothing to be scared of, as long as we don't go outside. "
        "Nobody else wants to be in charge, so I'm gonna try. Most of the kids listen to me already, so it should be easy."
    ),
    723: (
        "We're all okay. If you can call being stuck in a cave with 82 terrified kids okay. Alive, anyway. "
        "But I don't know what the hell we're going to do. It's been 4 days. Claudia went out this morning to look around, "
        "and never came back. Then Mr. Cob went out to look for her, and HE never came back either. "
        "So now there's only me, two other teachers, two of the parents who were chaperoning, and a few of the cavern staff. "
        "And all these poor kids. We've got enough food and water to last for awhile, I guess. But after that? "
        "I just don't know. We can't stay in here forever. Can we?"
    ),
    725: (
        "My name is Carrie Delaney. I teach fourth grade at the Early Dawn Elementary School, in Washington, D.C. "
        "Yesterday, October 23, 2077, half the school went on a field trip to Lamplight Caverns. "
        "We were packing up to leave when- when everything went crazy. The caves started shaking, the lights went out, "
        "the kids started screaming. My God... Mister Pollack went outside to see what was going on. "
        "When he came back in, he told us what he saw. Clouds. Mushroom clouds. It's finally happened. The end of the world."
    ),
}

base = Path(__file__).resolve().parent
import time

out = {}
for row, en in texts.items():
    out[row] = t.translate(en)
    time.sleep(1.5)
(base / "_holotape_mt.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("wrote", len(out), "holotapes")
