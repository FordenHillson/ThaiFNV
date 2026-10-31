#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""names_compact_pack.py — Compact Unique Pack สำหรับแปล FNV_Names ด้วย Cursor agent"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEETS = ROOT / "extracted" / "sheets"
CSV_PATH = SHEETS / "FNV_Names.csv"
PACK_ROOT = SHEETS / "names_packs"
IN_DIR = PACK_ROOT / "in"
OUT_DIR = PACK_ROOT / "out"
INDEX_PATH = PACK_ROOT / "en_index.json"
GLOSSARY = ROOT / "corpus" / "names_glossary_short.md"

PACK_SIZE_MIN = 80
PACK_SIZE_MAX = 100

EDITORID_LIKE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])[A-Za-z0-9_]+$")

FIELDS = ["ID", "ประเภท", "FormID", "EditorID", "EN", "TH", "สถานะ", "หมายเหตุ"]


def load_proper_nouns(glossary_path: Path) -> frozenset[str]:
    text = glossary_path.read_text(encoding="utf-8")
    nouns: set[str] = set()
    in_keep = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_keep = "คง EN" in line
            continue
        if not in_keep or not line.strip() or line.strip().startswith("|"):
            continue
        for part in line.split(","):
            token = part.strip()
            if token:
                nouns.add(token)
    return frozenset(nouns)


def classify_en(en: str, proper: frozenset[str]) -> tuple[str, str]:
    s = (en or "").strip()
    if not s:
        return ("keep", "empty")
    if s in proper:
        return ("keep", "proper-noun")
    if " " not in s and EDITORID_LIKE.match(s):
        return ("keep", "editorid-like")
    return ("need_ai", "")


def build_unique_index(rows: list[dict], proper: frozenset[str]) -> dict:
    seen: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        en = (r.get("EN") or "").strip()
        if en in seen:
            continue
        bucket, note = classify_en(en, proper)
        seen[en] = {"en": en, "bucket": bucket, "note": note, "n": None}
        order.append(en)
    n = 0
    entries = []
    for en in order:
        e = seen[en]
        if e["bucket"] == "need_ai":
            n += 1
            e["n"] = n
        entries.append(e)
    return {"version": 1, "source": "FNV_Names.csv", "entries": entries, "packs": []}


def write_packs(index: dict, in_dir: Path, pack_size: int = 100) -> list[str]:
    in_dir.mkdir(parents=True, exist_ok=True)
    need = [e for e in index["entries"] if e["bucket"] == "need_ai"]
    packs = []
    pack_ids = []
    for i in range(0, len(need), pack_size):
        chunk = need[i : i + pack_size]
        pid = f"u_{len(pack_ids) + 1:04d}"
        path = in_dir / f"{pid}.tsv"
        lines = [f"{e['n']}\t{e['en']}" for e in chunk]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        packs.append(
            {
                "id": pid,
                "n_from": chunk[0]["n"],
                "n_to": chunk[-1]["n"],
                "count": len(chunk),
            }
        )
        pack_ids.append(pid)
    index["packs"] = packs
    return pack_ids


def validate_out_pack(in_path: Path, out_path: Path) -> list[str]:
    errs: list[str] = []
    if not out_path.exists():
        return [f"missing out: {out_path.name}"]
    in_lines = [ln for ln in in_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out_lines = [ln for ln in out_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(in_lines) != len(out_lines):
        errs.append(f"line count {len(out_lines)} != {len(in_lines)}")
    in_ns = []
    out_map: dict[str, str] = {}
    for ln in in_lines:
        parts = ln.split("\t")
        if len(parts) != 2:
            errs.append(f"bad in line: {ln!r}")
            continue
        in_ns.append(parts[0])
    for ln in out_lines:
        parts = ln.split("\t")
        if len(parts) != 2:
            errs.append(f"bad out line: {ln!r}")
            continue
        n, th = parts[0], parts[1]
        if not th.strip():
            errs.append(f"empty TH for n={n}")
        if n in out_map:
            errs.append(f"duplicate n={n}")
        out_map[n] = th
    for n in in_ns:
        if n not in out_map:
            errs.append(f"missing n={n}")
    return errs


def _load_out_n_to_th(out_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not out_path.exists():
        return mapping
    for ln in out_path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) == 2:
            mapping[parts[0]] = parts[1]
    return mapping


def build_en_to_th(
    index: dict,
    out_dir: Path,
    in_dir: Path | None = None,
) -> dict[str, tuple[str, str, str]]:
    if in_dir is not None:
        all_errs: list[str] = []
        for pack in index.get("packs", []):
            pid = pack["id"]
            errs = validate_out_pack(in_dir / f"{pid}.tsv", out_dir / f"{pid}.tsv")
            for e in errs:
                all_errs.append(f"{pid}: {e}")
        if all_errs:
            raise ValueError("; ".join(all_errs))

    n_to_th: dict[str, str] = {}
    for pack in index.get("packs", []):
        n_to_th.update(_load_out_n_to_th(out_dir / f"{pack['id']}.tsv"))

    en_map: dict[str, tuple[str, str, str]] = {}
    for entry in index["entries"]:
        en = entry["en"]
        bucket = entry["bucket"]
        note = entry.get("note") or ""
        if bucket == "keep":
            en_map[en] = (en, "keep", note)
        elif bucket == "need_ai":
            n = entry.get("n")
            if n is None:
                continue
            th = n_to_th.get(str(n), "")
            en_map[en] = (th, "ai", note)
    return en_map


def merge_into_rows(
    rows: list[dict],
    en_map: dict[str, tuple[str, str, str]],
) -> tuple[int, int]:
    filled = 0
    skipped = 0
    for row in rows:
        en = (row.get("EN") or "").strip()
        if en not in en_map:
            skipped += 1
            continue
        th_existing = (row.get("TH") or "").strip()
        status = (row.get("สถานะ") or "").strip()
        if th_existing or status in {"ok", "fix"}:
            skipped += 1
            continue
        th, st, note = en_map[en]
        row["TH"] = th
        row["สถานะ"] = st
        row["หมายเหตุ"] = note
        filled += 1
    return filled, skipped


def atomic_write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _load_index() -> dict:
    if not INDEX_PATH.is_file():
        raise SystemExit(f"missing index: {INDEX_PATH}")
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _save_index(index: dict) -> None:
    PACK_ROOT.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _out_pack_files(out_dir: Path) -> list[Path]:
    if not out_dir.is_dir():
        return []
    return sorted(out_dir.glob("*.tsv"))


def _require_force_if_out_has_packs(out_dir: Path, force: bool) -> None:
    existing = _out_pack_files(out_dir)
    if not existing or force:
        return
    sample = ", ".join(p.name for p in existing[:5])
    if len(existing) > 5:
        sample = f"{sample} (+{len(existing) - 5} more)"
    print(
        "error: build will reset in/*.tsv and regenerate en_index.json, but "
        f"out/ already has {len(existing)} translated pack file(s) "
        f"({sample}). "
        "Aborting to avoid breaking in/out pairing for merge. "
        "Run merge first, or pass --force to rebuild in/ anyway (out/ is not deleted).",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _reset_in_dir(in_dir: Path) -> None:
    in_dir.mkdir(parents=True, exist_ok=True)
    for p in in_dir.glob("*.tsv"):
        p.unlink()


def _validate_pack_size(pack_size: int) -> None:
    if not PACK_SIZE_MIN <= pack_size <= PACK_SIZE_MAX:
        raise SystemExit(
            f"pack-size must be {PACK_SIZE_MIN}-{PACK_SIZE_MAX}, got {pack_size}"
        )


def cmd_build(args: argparse.Namespace) -> None:
    _validate_pack_size(args.pack_size)
    if not CSV_PATH.is_file():
        raise SystemExit(f"missing CSV: {CSV_PATH}")
    if not GLOSSARY.is_file():
        raise SystemExit(f"missing glossary: {GLOSSARY}")

    _require_force_if_out_has_packs(OUT_DIR, getattr(args, "force", False))

    rows = _read_csv(CSV_PATH)
    proper = load_proper_nouns(GLOSSARY)
    index = build_unique_index(rows, proper)
    _reset_in_dir(IN_DIR)
    write_packs(index, IN_DIR, pack_size=args.pack_size)
    _save_index(index)

    entries = index["entries"]
    unique = len(entries)
    keep = sum(1 for e in entries if e["bucket"] == "keep")
    need_ai = sum(1 for e in entries if e["bucket"] == "need_ai")
    packs = len(index["packs"])
    print(f"unique={unique} keep={keep} need_ai={need_ai} packs={packs}")


def cmd_merge(_args: argparse.Namespace) -> None:
    index = _load_index()
    merge_index = copy.deepcopy(index)
    merge_index["packs"] = [
        p
        for p in index.get("packs", [])
        if (OUT_DIR / f"{p['id']}.tsv").is_file()
    ]
    en_map = build_en_to_th(merge_index, OUT_DIR, IN_DIR)
    en_map = {
        en: val
        for en, val in en_map.items()
        if val[1] != "ai" or val[0].strip()
    }
    rows = _read_csv(CSV_PATH)
    filled, skipped = merge_into_rows(rows, en_map)
    atomic_write_csv(CSV_PATH, rows)
    print(f"filled={filled} skipped={skipped}")


def cmd_status(_args: argparse.Namespace) -> None:
    if not CSV_PATH.is_file():
        raise SystemExit(f"missing CSV: {CSV_PATH}")
    rows = _read_csv(CSV_PATH)
    th_empty = sum(1 for r in rows if not (r.get("TH") or "").strip())

    done = 0
    pending = 0
    if INDEX_PATH.is_file():
        index = _load_index()
        for pack in index.get("packs", []):
            out_path = OUT_DIR / f"{pack['id']}.tsv"
            if out_path.is_file():
                done += 1
            else:
                pending += 1

    print(f"TH empty: {th_empty}")
    print(f"packs done: {done} pending: {pending}")


def cmd_next(_args: argparse.Namespace) -> None:
    index = _load_index()
    for pack in index.get("packs", []):
        in_path = IN_DIR / f"{pack['id']}.tsv"
        out_path = OUT_DIR / f"{pack['id']}.tsv"
        if in_path.is_file() and not out_path.is_file():
            print(in_path.resolve())
            return
    print("(no pending packs)")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compact unique packs for FNV_Names AI translation",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="build index and in/ packs from CSV")
    p_build.add_argument(
        "--pack-size",
        type=int,
        default=100,
        help=f"lines per pack ({PACK_SIZE_MIN}-{PACK_SIZE_MAX}, default 100)",
    )
    p_build.add_argument(
        "--force",
        action="store_true",
        help="allow rebuild when out/ already has translated packs",
    )
    p_build.set_defaults(func=cmd_build)

    p_merge = sub.add_parser("merge", help="merge keep + out packs into CSV")
    p_merge.set_defaults(func=cmd_merge)

    p_status = sub.add_parser("status", help="show TH gaps and pack progress")
    p_status.set_defaults(func=cmd_status)

    p_next = sub.add_parser("next", help="path to first in pack without out")
    p_next.set_defaults(func=cmd_next)

    args = ap.parse_args()
    try:
        args.func(args)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
