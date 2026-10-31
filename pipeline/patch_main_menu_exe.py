#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_main_menu_exe.py — แพตช์ข้อความ UI ใน FalloutNV.exe (เมนู/ตั้งค่า/companion/pipboy)

Usage:
  python patch_main_menu_exe.py
  python patch_main_menu_exe.py --restore
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from thai_precompose import encode_thai_cp874

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_EXE = Path(r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\FalloutNV.exe")

# (context_before_value, english_value, thai) — thai ต้องไม่ยาวกว่าช่อง EN (ไม่นับ NUL)
PATCHES: list[tuple[bytes, str, str]] = [
    # main menu
    (b"sContinue\x00\x00\x00", "Continue", "เล่นต่อ"),
    (b"sNew\x00\x00\x00\x00", "New", "นิว"),
    (b"sLoad\x00\x00\x00", "Load", "โหลด"),
    (b"sSettings\x00\x00\x00", "Settings", "ตั้งค่า"),
    (b"sCrew\x00\x00\x00", "Credits", "เครดิต"),
    (b"sDownloads\x00\x00", "Downloadable Content", "เนื้อหาดาวน์โหลด"),
    (b"sQuit\x00\x00\x00", "Quit", "ออก"),
    (b"sSave\x00\x00\x00", "Save", "เซฟ"),
    # confirm
    (
        b"sConfirmNew\x00\x00\x00\x00\x00",
        "Start a new game? This will\noverwrite your Autosave if present.",
        "เริ่มเกมใหม่?\nจะทับ Autosave ถ้ามี",
    ),
    (b"sYesText\x00\x00\x00\x00", "&Yes", "ใช่"),
    (b"sNoText\x00", "&No", "ไม่"),
    # settings categories
    (b"sGameplay\x00\x00\x00", "Gameplay", "การเล่น"),
    (b"sControls\x00\x00\x00", "Controls", "ควบคุม"),
    (b"sDefaults\x00\x00\x00", "Defaults", "ค่าเริ่ม"),
    (b"sVideo\x00\x00", "Video", "วิดีโอ"),
    # gameplay options
    (b"sKillCamMode\x00\x00\x00\x00", "Kill Cam Mode", "โหมดคิลแคม"),
    (b"sHardcore\x00\x00\x00", "Hardcore Mode", "โหมดฮาร์ดคอร์"),
    (b"sDifficulty\x00", "Difficulty", "ความยาก"),
    (b"sSaveOnRest\x00", "Save On Rest", "เซฟตอนพัก"),
    (b"sSaveOnWait\x00", "Save On Wait", "เซฟตอนรอ"),
    (b"sSaveOnTravel\x00\x00\x00", "Save On Travel", "เซฟตอนเดินทาง"),
    (b"sTrueIronSights\x00", "True Iron Sights", "เล็งปากกระบอก"),
    (b"sKillCamModePlayer\x00\x00", "Player View", "มุมผู้เล่น"),
    (b"sKillCamModeCinematic\x00\x00\x00", "Cinematic", "ภาพยนตร์"),
    # pip-boy tabs
    (b"sStats\x00\x00", "STATS", "สถานะ"),
    (b"sStatsStatus\x00\x00\x00\x00", "Status", "สถานะ"),
    (b"sStatsSpecial\x00\x00\x00", "S.P.E.C.I.A.L.", "SPECIAL"),
    (b"sStatsSkills\x00\x00\x00\x00", "Skills", "ทักษะ"),
    (b"sStatsPerks\x00", "Perks", "เพิร์ก"),
    (b"sStatsCondition\x00", "Condition", "สภาพ"),
    # companion wheel
    (b"sCWheelTitle\x00\x00\x00\x00", "Companion Commands", "คำสั่งเพื่อน"),
    (b"sCWheelBeAggressive\x00", "Be Aggressive", "ก้าวร้าว"),
    (b"sCWheelBePassive\x00\x00\x00\x00", "Be Passive", "ตั้งรับ"),
    (b"sCWheelUseStimpak\x00\x00\x00", "Use Stimpak", "ใช้สติมแพค"),
    (b"sCWheelWaitHere\x00", "Wait Here", "รอที่นี่"),
    (b"sCWheelFollowMe\x00", "Follow Me", "ตามมา"),
    (b"sCWheelTalkTo\x00\x00\x00", "Talk To", "คุยกับ"),
    (b"sCWheelBackUp\x00\x00\x00", "Back Up", "ถอยหลัง"),
    (b"sCWheelStayClose\x00\x00\x00\x00", "Stay Close", "อยู่ใกล้"),
    (b"sCWheelKeepDistance\x00", "Keep Distance", "รักษาระยะ"),
    (b"sCWheelOpenInventory\x00\x00\x00\x00", "Open Inventory", "เปิดกระเป๋า"),
    (b"sCWheelUseRanged\x00\x00\x00\x00", "Use Ranged", "ใช้ระยะไกล"),
    (b"sCWheelUseMelee\x00", "Use Melee", "ใช้ประชิด"),
]


def patch_one(data: bytearray, ctx: bytes, en: str, th: str) -> bool:
    en_b = en.encode("ascii") + b"\x00"
    th_b = encode_thai_cp874(th) + b"\x00"
    needle = ctx + en_b
    i = data.find(needle)
    if i < 0:
        j = data.find(ctx)
        if j >= 0:
            print("MISS %r (อาจแพตช์แล้ว) ctx@0x%X" % (en[:40], j))
        else:
            print("MISS %r (ไม่พบ context)" % (en[:40],))
        return False
    abs_i = i + len(ctx)
    old_len = len(en_b)
    if len(th_b) > old_len:
        print(
            "SKIP %r → %r (thai %d > slot %d)"
            % (en[:40], th, len(th_b) - 1, old_len - 1)
        )
        return False
    padded = th_b + (b"\x00" * (old_len - len(th_b)))
    data[abs_i : abs_i + old_len] = padded
    print("OK  %r → %r" % (en[:40], th))
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--restore", action="store_true")
    ap.add_argument(
        "--from-bak",
        action="store_true",
        help="เริ่มจาก backup แล้วแพตช์ใหม่ทั้งหมด",
    )
    args = ap.parse_args()
    exe = Path(args.exe)
    bak = exe.with_suffix(exe.suffix + ".thaifnv.bak")

    if args.restore:
        if not bak.exists():
            raise SystemExit("ไม่มี backup: %s" % bak)
        shutil.copy2(bak, exe)
        print("restored %s from %s" % (exe, bak))
        return

    if not exe.exists():
        raise SystemExit("ไม่พบ exe: %s" % exe)

    if args.from_bak:
        if not bak.exists():
            raise SystemExit("ไม่มี backup: %s" % bak)
        data = bytearray(bak.read_bytes())
        print("base = backup")
    else:
        data = bytearray(exe.read_bytes())
        if not bak.exists():
            shutil.copy2(exe, bak)
            print("backup → %s" % bak)
        else:
            print("backup มีอยู่แล้ว: %s" % bak)

    n = 0
    for ctx, en, th in PATCHES:
        if patch_one(data, ctx, en, th):
            n += 1
    exe.write_bytes(data)
    print("patched %d / %d → %s" % (n, len(PATCHES), exe))


if __name__ == "__main__":
    main()
