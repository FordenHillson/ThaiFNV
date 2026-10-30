#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump ThaiFNV_Test.esp records fully for encoding/content evidence."""
from __future__ import annotations
import json
import os
import struct
import time
import zlib

PATH = r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data\ThaiFNV_Test.esp"
LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".cursor", "debug-8f0ee2.log")
FLAG_COMPRESSED = 0x00040000


def dlog(msg, data):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "sessionId": "8f0ee2", "runId": "esp-dump", "hypothesisId": "K",
            "location": "debug_dump_esp.py", "message": msg, "data": data,
            "timestamp": int(time.time() * 1000),
        }, ensure_ascii=False) + "\n")


def decode_best(raw: bytes):
    raw = raw.split(b"\x00")[0]
    for enc in ("cp874", "utf-8", "latin-1"):
        try:
            return enc, raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return "?", raw.hex()


def walk(data: bytes):
    records = []
    off = 0
    while off + 24 <= len(data):
        tag = data[off:off + 4]
        if tag == b"GRUP":
            # group header: 24 bytes, size includes header
            gsize = struct.unpack_from("<I", data, off + 4)[0]
            label = data[off + 8:off + 12]
            records.append({"kind": "GRUP", "label": label.decode("latin-1", "replace"),
                            "size": gsize, "at": off})
            off += 24
            continue
        rtype = tag.decode("ascii", "replace")
        dsize = struct.unpack_from("<I", data, off + 4)[0]
        flags = struct.unpack_from("<I", data, off + 8)[0]
        formid = struct.unpack_from("<I", data, off + 12)[0]
        payload = data[off + 24:off + 24 + dsize]
        if flags & FLAG_COMPRESSED and payload:
            try:
                payload = zlib.decompress(payload[4:]) if len(payload) > 4 else payload
            except Exception:
                try:
                    payload = zlib.decompress(payload)
                except Exception:
                    payload = b""
        subs = []
        so = 0
        while so + 6 <= len(payload):
            st = payload[so:so + 4].decode("ascii", "replace")
            ss = struct.unpack_from("<H", payload, so + 4)[0]
            sb = payload[so + 6:so + 6 + ss]
            enc, txt = decode_best(sb) if ss else ("", "")
            subs.append({
                "type": st, "size": ss,
                "enc": enc, "text": txt if isinstance(txt, str) else str(txt),
                "hex": sb[:40].hex(),
                "n_cp874": None,
            })
            if isinstance(txt, str) and enc == "cp874":
                # verify roundtrip
                try:
                    subs[-1]["n_cp874"] = len(txt.encode("cp874"))
                except Exception:
                    subs[-1]["n_cp874"] = -1
            so += 6 + ss
            if ss == 0 and st.strip() == "":
                break
        records.append({
            "kind": "REC", "type": rtype, "formid": "%08X" % formid,
            "flags": flags, "dsize": dsize, "subs": subs, "at": off,
        })
        off += 24 + dsize
    return records


def main():
    data = open(PATH, "rb").read()
    recs = walk(data)
    # print human
    for r in recs:
        if r["kind"] == "GRUP":
            print("GRUP", r["label"], "size", r["size"])
            continue
        print("REC", r["type"], r["formid"], "subs", len(r["subs"]))
        for s in r["subs"]:
            if s["type"] in ("EDID", "FULL", "DESC", "ITXT", "NNAM", "DATA"):
                print(" ", s["type"], "size", s["size"], "enc", s["enc"],
                      "cp874_len", s["n_cp874"], ":", repr(s["text"][:200]))
    dlog("ThaiFNV_Test.esp full dump", {"size": len(data), "records": recs})


if __name__ == "__main__":
    main()
