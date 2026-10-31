#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_exe_ui.py — ดึงข้อความ UI จาก FalloutNV.exe (GameSetting s*)

Usage:
  python extract_exe_ui.py
  python extract_exe_ui.py --exe path\\FalloutNV.exe.thaifnv.bak
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "extracted" / "sheets" / "FNV_ExeUI.csv"
FIELDS = ["ID", "ประเภท", "FormID", "EditorID", "EN", "TH", "สถานะ", "หมายเหตุ"]

DEFAULT_EXE = Path(
    r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\FalloutNV.exe.thaifnv.bak"
)
FALLBACK_EXE = Path(r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\FalloutNV.exe")

# sName มาตรฐานของ GameSetting (ขึ้นต้น s แล้วตามด้วยตัวพิมพ์ใหญ่)
EDID_RE = re.compile(rb"(s[A-Z][A-Za-z0-9]{1,48})\x00+")
# ช่วง .rdata ที่มีบล็อก UI (จาก REA / การไล่ก่อนหน้า)
# ถ้าไม่เจอลายเซ็น จะสแกนทั้งไฟล์แล้วกรองเข้ม
ANCHORS = [
    b"sPressStart\x00",
    b"sConfirmNew\x00",
    b"sCWheelTitle\x00",
    b"sTrueIronSights\x00",
    b"sHUDOpacity\x00",
    b"sKillCamMode\x00",
]


def decode_en(raw: bytes) -> str | None:
    if not raw or len(raw) > 500:
        return None
    # ขยะ binary
    if any(b < 9 or (13 < b < 32 and b != 10) for b in raw):
        return None
    try:
        en = raw.decode("cp1252")
    except Exception:
        return None
    en = en.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not en:
        return None
    if not any(c.isalpha() for c in en):
        return None
    # path / format junk
    if en.startswith(("Interface\\", "Data\\", "Meshes\\", "Textures\\", "%s", "%i", "%d", "%f")):
        return None
    if en.count("\\") >= 2:
        return None
    return en


def _looks_like_edid(raw: bytes) -> bool:
    """ค่าที่ดึงมาเป็น sSomething (= edid ถัดไป) ไม่ใช่ข้อความ UI"""
    if not raw.startswith(b"s") or len(raw) < 3:
        return False
    if not (65 <= raw[1] <= 90):  # A-Z
        return False
    return all(48 <= b <= 57 or 65 <= b <= 90 or 97 <= b <= 122 for b in raw[1:])


def _humanize_edid(edid: str) -> str:
    """sHUDOpacity → HUD Opacity (หยาบ ๆ สำหรับตัวที่ไม่มี value ใน exe)"""
    core = edid[1:] if edid.startswith("s") else edid
    # แยกคำแบบ camel
    parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", core)
    return " ".join(parts) if parts else core


def extract_from_region(data: bytes, start: int, end: int) -> dict[str, str]:
    """map EditorID → EN จากช่วงไบต์"""
    found: dict[str, str] = {}
    pos = start
    while pos < end:
        m = EDID_RE.search(data, pos, end)
        if not m:
            break
        edid = m.group(1).decode("ascii")
        val_start = m.end()
        z = data.find(b"\x00", val_start, min(val_start + 500, end))
        if z < 0:
            pos = m.end()
            continue
        raw = data[val_start:z]
        if raw.startswith(b"&") and len(raw) > 1:
            raw = raw[1:]
        if _looks_like_edid(raw) or len(raw) == 0:
            en = _humanize_edid(edid)
        else:
            en = decode_en(raw)
            if en is None:
                en = _humanize_edid(edid)
        if en and edid not in found:
            found[edid] = en
        pos = m.end()
    return found


def guess_windows(data: bytes) -> list[tuple[int, int]]:
    """หาหน้าต่างรอบ anchor แต่ละจุด"""
    windows = []
    for a in ANCHORS:
        i = data.find(a)
        if i < 0:
            continue
        windows.append((max(0, i - 2000), min(len(data), i + 12000)))
    if not windows:
        # ทั้งไฟล์ — จะกรองทีหลัง
        return [(0, len(data))]
    # รวมช่วงที่ซ้อน
    windows.sort()
    merged = [windows[0]]
    for s, e in windows[1:]:
        ps, pe = merged[-1]
        if s <= pe:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


# allowlist กลุ่มที่เกี่ยวกับ UI จาก screenshot / เมนู
PREFIX_KEEP = (
    "sConfirm",
    "sCWheel",
    "sStats",
    "sHUD",
    "sPip",
    "sSave",
    "sKill",
    "sHard",
    "sDiff",
    "sTrue",
    "sGrass",
    "sShadow",
    "sLight",
    "sSpec",
    "sObject",
    "sTree",
    "sActor",
    "sItem",
    "sCross",
    "sDialog",
    "sGeneral",
    "sBright",
    "sResol",
    "sText",
    "sView",
    "sGame",
    "sCont",
    "sDef",
    "sVid",
    "sAud",
    "sDisp",
    "sNew",
    "sLoad",
    "sSett",
    "sCrew",
    "sQuit",
    "sDown",
    "sBack",
    "sNext",
    "sPrev",
    "sExit",
    "sYes",
    "sNo",
    "sPress",
    "sMain",
    "sInven",
    "sMagic",
    "sLevel",
    "sVDSG",
    "sAmmo",
    "sWeap",
    "sArmor",
    "sHelp",
    "sDisable",
    "sEnable",
    "sAccept",
    "sCancel",
    "sClose",
    "sDone",
    "sOK",
    "sRumble",
    "sAuto",
    "sManual",
    "sOn",
    "sOff",
    "sNone",
    "sMale",
    "sFemale",
    "sPlay",
    "sPause",
    "sResume",
    "sReturn",
    "sDevice",
    "sRedeem",
    "sMust",
    "sCant",
    "sPlease",
    "sLoading",
    "sStart",
    "sContinue",
    "sMissing",
    "sOver",
    "sNoSleep",
    "sNoWait",
    "sTrait",
    "sRace",
    "sAge",
    "sName",
    "sWeight",
    "sHair",
    "sFace",
    "sTone",
    "sColor",
    "sSize",
    "sStyle",
    "sReset",
    "sMake",
    "sVersion",
    "sKarma",
    "sRep",
    "sQuest",
    "sMap",
    "sRadio",
    "sNote",
    "sMisc",
    "sChems",
    "sFood",
    "sAid",
    "sApparel",
    "sWeapons",
    "sMods",
    "sQTY",
    "sValue",
    "sWeight",
    "sCondition",
    "sHealth",
    "sAction",
    "sDamage",
    "sDT",
    "sDR",
    "sSpread",
    "sCrit",
    "sSkill",
    "sPerk",
    "sSpecial",
    "sAttribute",
    "sBarter",
    "sRepair",
    "sSneak",
    "sSpeech",
    "sScience",
    "sMedicine",
    "sSurvival",
    "sLockpick",
    "sExplosives",
    "sUnarmed",
    "sMelee",
    "sGuns",
    "sEnergy",
    "sFind",
    "sSort",
    "sDrop",
    "sEquip",
    "sUnequip",
    "sHotkey",
    "sWait",
    "sSleep",
    "sRest",
    "sTravel",
    "sFast",
    "sWorld",
    "sLocal",
    "sUnknown",
    "sEmpty",
    "sFull",
    "sTotal",
    "sRequired",
    "sOptional",
    "sFailure",
    "sSuccess",
    "sHack",
    "sLock",
    "sUnlock",
    "sTerminal",
    "sComputer",
    "sNoteAdded",
    "sHoliday",
    "sMonth",
    "sDay",
    "sYear",
    "sAM",
    "sPM",
    "sTime",
    "sDate",
    "sHour",
    "sMinute",
    "sSecond",
    "sFPS",
    "sVSync",
    "sAnisotropic",
    "sAnti",
    "sWater",
    "sBlood",
    "sDecal",
    "sMulti",
    "sParticle",
    "sShadow",
    "sSpecular",
    "sRadial",
    "sSoft",
    "sHard",
    "sLow",
    "sMed",
    "sHigh",
    "sUltra",
    "sLarge",
    "sSmall",
    "sMedium",
    "sAmber",
    "sWhite",
    "sGreen",
    "sBlue",
    "sRed",
    "sDefault",
)


def keep_edid(edid: str) -> bool:
    if not edid.startswith("s") or len(edid) < 3:
        return False
    return any(edid.startswith(p) for p in PREFIX_KEEP)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="")
    ap.add_argument("--loose", action="store_true", help="ไม่กรอง prefix (ได้เยอะแต่มีขยะ)")
    args = ap.parse_args()
    exe = Path(args.exe) if args.exe else (
        DEFAULT_EXE if DEFAULT_EXE.exists() else FALLBACK_EXE
    )
    if not exe.exists():
        raise SystemExit("ไม่พบ exe: %s" % exe)
    data = exe.read_bytes()

    merged: dict[str, str] = {}
    # สแกนทั้งไฟล์ แต่เก็บเฉพาะ prefix UI (กันขยะจากโค้ด)
    for k, v in extract_from_region(data, 0, len(data)).items():
        if args.loose or keep_edid(k):
            merged.setdefault(k, v)

    # เติมตัวที่ไม่มี value ในตาราง — ใช้ชื่อ humanize
    for edid in ("sDisplay", "sAudio", "sInterface", "sTweaks", "sData", "sItems"):
        if edid not in merged and data.find(edid.encode("ascii") + b"\x00") >= 0:
            merged[edid] = _humanize_edid(edid)
    rows = []
    for edid in sorted(merged.keys()):
        if not args.loose and not keep_edid(edid):
            continue
        rows.append((edid, merged[edid]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for i, (edid, en) in enumerate(rows, 1):
            w.writerow(
                {
                    "ID": i,
                    "ประเภท": "EXE:STR",
                    "FormID": "",
                    "EditorID": edid,
                    "EN": en,
                    "TH": "",
                    "สถานะ": "",
                    "หมายเหตุ": "FalloutNV.exe UI string",
                }
            )
    print("wrote %s (%d rows) from %s" % (OUT, len(rows), exe))


if __name__ == "__main__":
    main()
