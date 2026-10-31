#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repair_sheet_formids.py — ซ่อม FormID จาก CSV ต้นทาง

ปัญหาที่พบบ่อยจาก Google Sheets:
  - 000003E8 ถูกอ่านเป็น scientific 3E8 → 300000000
  - 000003E9 → 3000000000
  - leading zero หาย (00000452 → 452)

Usage:
  python repair_sheet_formids.py
  python repair_sheet_formids.py --force-local
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "extracted" / "sheets"
GOOGLE = LOCAL / "from_google"
FIELDS = ["ID", "ประเภท", "FormID", "EditorID", "EN", "TH", "สถานะ", "หมายเหตุ"]


def normalize_hex(fid: str) -> str | None:
    s = (fid or "").strip().replace("0x", "").replace("0X", "")
    if not s:
        return None
    if "E+" in s.upper() or "E-" in s.upper() or "." in s:
        return None
    try:
        v = int(s, 16)
    except ValueError:
        return None
    if v < 0 or v > 0xFFFFFFFF:
        return None
    return f"{v:08X}"


def is_suspicious(fid: str, local_fid: str | None) -> bool:
    """True ถ้าควรแทนที่ด้วยค่าจาก local"""
    if local_fid:
        nh = normalize_hex(fid)
        lh = normalize_hex(local_fid)
        if lh and nh != lh:
            return True
    nh = normalize_hex(fid)
    if nh is None:
        return True
    # scientific แปลงแล้ว เช่น 3E8 → 300000000 (ไม่มีตัวอักษร A-F บางทีก็ยังเพี้ยน)
    raw = (fid or "").strip()
    if raw.upper().startswith("3") and len(raw) >= 9 and "E" not in raw.upper():
        # 300000000 / 3000000000 จาก 3E8/3E9
        if raw in ("300000000", "3000000000", "30000000"):
            return True
    return False


def normalize_row(r: dict) -> dict:
    out = dict(r)
    if "ID" not in out and "I" in out:
        out["ID"] = out.pop("I")
    for k in FIELDS:
        out.setdefault(k, "")
    return out


def load_local_maps(name: str) -> tuple[dict, dict, dict]:
    path = LOCAL / f"{name}.csv"
    by_key: dict[tuple[str, str, str], str] = {}
    by_edid_typ: dict[tuple[str, str], str] = {}
    by_en: dict[tuple[str, str], str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            fid = normalize_hex(r.get("FormID") or "")
            if not fid:
                continue
            # เก็บแบบ 8 หลัก / ตามต้นทาง
            raw = (r.get("FormID") or "").strip()
            edid = r.get("EditorID") or ""
            typ = r.get("ประเภท") or ""
            en = r.get("EN") or ""
            by_key[(edid, typ, en)] = raw
            if edid:
                by_edid_typ[(edid, typ)] = raw
            by_en[(typ, en)] = raw
    return by_key, by_edid_typ, by_en


def repair_tab(name: str, force_local: bool) -> tuple[int, int]:
    src = GOOGLE / f"{name}.csv"
    if not src.exists():
        print("SKIP missing %s" % src)
        return 0, 0
    by_key, by_edid_typ, by_en = load_local_maps(name)
    rows_in = list(csv.DictReader(src.open(encoding="utf-8-sig", newline="")))
    fixed = 0
    still = 0
    out_rows = []
    for raw in rows_in:
        r = normalize_row(raw)
        edid = r.get("EditorID") or ""
        typ = r.get("ประเภท") or ""
        en = r.get("EN") or ""
        fid = (r.get("FormID") or "").strip()
        local = (
            by_key.get((edid, typ, en))
            or by_edid_typ.get((edid, typ))
            or by_en.get((typ, en))
        )
        if force_local and local:
            if fid != local:
                r["FormID"] = local
                fixed += 1
        elif local and is_suspicious(fid, local):
            r["FormID"] = local
            fixed += 1
        elif normalize_hex(fid) is None:
            if local:
                r["FormID"] = local
                fixed += 1
            else:
                still += 1
        out_rows.append({k: r.get(k, "") for k in FIELDS})
    with src.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print("OK  %-20s fixed=%d still_bad=%d rows=%d" % (name, fixed, still, len(out_rows)))
    return fixed, still


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tabs", default="")
    ap.add_argument(
        "--force-local",
        action="store_true",
        help="ทับ FormID ด้วยค่าจาก local ทุกแถวที่จับคู่ได้",
    )
    args = ap.parse_args()
    if args.tabs:
        names = [t.strip() for t in args.tabs.split(",") if t.strip()]
    else:
        names = sorted(p.stem for p in GOOGLE.glob("FNV_*.csv"))
    total_f = total_s = 0
    for name in names:
        if not (LOCAL / f"{name}.csv").exists():
            print("SKIP no local extract for %s" % name)
            continue
        f, s = repair_tab(name, args.force_local)
        total_f += f
        total_s += s
    print("done fixed=%d still_bad=%d" % (total_f, total_s))


if __name__ == "__main__":
    main()
