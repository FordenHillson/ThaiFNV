#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import struct
import time
import zlib

PATH = r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\ThaiFNV_Test.esp"
LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".cursor", "debug-8f0ee2.log")


def dlog(hid, msg, data):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "sessionId": "8f0ee2", "runId": "esp-inspect", "hypothesisId": hid,
            "location": "debug_inspect_esp.py", "message": msg, "data": data,
            "timestamp": int(time.time() * 1000),
        }, ensure_ascii=False) + "\n")


def main():
    data = open(PATH, "rb").read()
    print("size", len(data))
    findings = []
    probes = [
        ("title", "หุ่นยนต์ Duraframe Eyebot ที่เสียหาย"),
        ("desc", "ดูเหมือนว่า"),
        ("btn", "ปล่อยมัน"),
        ("en_title", "Damaged Duraframe"),
        ("en_servo", "servos"),
        ("en_leave", "Leave It Alone"),
    ]
    for label, s in probes:
        for enc in ("cp874", "utf-8", "utf-16-le"):
            try:
                b = s.encode(enc)
            except UnicodeEncodeError:
                continue
            i = data.find(b)
            findings.append({
                "label": label, "enc": enc, "found": i >= 0, "at": i,
                "nbytes": len(b), "head": b[:12].hex(),
            })
            print(label, enc, "FOUND" if i >= 0 else "no", "at", i)

    # printable runs with high bytes
    runs = []
    cur = bytearray()
    start = 0
    for i, c in enumerate(data + b"\x00"):
        if 32 <= c < 127 or c >= 0xA0:
            if not cur:
                start = i
            cur.append(c)
        else:
            if len(cur) >= 4:
                raw = bytes(cur)
                decoded = None
                enc_used = None
                for enc in ("utf-8", "cp874", "latin-1"):
                    try:
                        t = raw.decode(enc)
                        enc_used = enc
                        decoded = t
                        break
                    except UnicodeDecodeError:
                        continue
                if decoded and (any(ord(ch) > 127 for ch in decoded) or any(
                        k in decoded for k in ("Eye", "servo", "Leave", "Dura", "Scrap"))):
                    runs.append({"at": start, "enc": enc_used, "text": decoded[:160]})
                    print("@%d [%s] %r" % (start, enc_used, decoded[:120]))
            cur = bytearray()

    dlog("K", "ThaiFNV_Test.esp string encoding probe", {
        "path": PATH, "size": len(data), "findings": findings, "runs": runs,
    })


if __name__ == "__main__":
    main()
