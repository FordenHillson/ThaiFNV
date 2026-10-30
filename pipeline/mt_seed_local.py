#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mt_seed_local.py — MT seed นอก Apps Script

แปล EN→TH แล้วตั้งสถานะ=mt · ข้ามแถวที่มี TH / ok|fix
แปลเฉพาะ EN ที่ไม่ซ้ำ (cache) · เซฟทุก --save-every · รันซ้ำต่อได้

Usage:
  python mt_seed_local.py extracted/sheets/FNV_Notes.csv --engine mymemory
  python mt_seed_local.py extracted/sheets/FNV_Notes.csv extracted/sheets/FNV_Quests.csv
  python mt_seed_local.py --queue remaining
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SHEETS = ROOT / "extracted" / "sheets"
OUT_DIR = SHEETS / "from_google"
CACHE_PATH = OUT_DIR / "_mt_cache.json"
FIELDS = ["ID", "ประเภท", "FormID", "EditorID", "EN", "TH", "สถานะ", "หมายเหตุ"]

QUEUE_REMAINING = [
    "FNV_Notes",
    "FNV_Quests",
    "FNV_Terminals",
    "FNV_Names",
    "FNV_TopicNames",
    "FNV_Dialogue",
]


def load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict[str, str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8"
    )


def make_translator(engine: str):
    from deep_translator import GoogleTranslator, MyMemoryTranslator

    engine = engine.lower()
    if engine == "translators":
        import translators as ts

        return ("translators", ts)
    if engine == "google":
        return ("google", GoogleTranslator(source="en", target="th"))
    if engine == "mymemory":
        return ("mymemory", MyMemoryTranslator(source="en-US", target="th-TH"))
    # auto: prefer mymemory (google มักโดนโควต้าหลัง Apps Script)
    return ("mymemory", MyMemoryTranslator(source="en-US", target="th-TH"))


def _chunk_text(text: str, limit: int = 450) -> list[str]:
    """MyMemory จำกัด ~500 ตัวอักษร — ตัดตามย่อหน้า/ประโยค"""
    text = text or ""
    if len(text) <= limit:
        return [text] if text else []
    parts: list[str] = []
    buf = ""
    # แยกย่อหน้าก่อน แล้วประโยค
    blocks = text.replace("\r\n", "\n").split("\n")
    units: list[str] = []
    for b in blocks:
        if not b.strip():
            units.append("\n")
            continue
        sents = re.split(r"(?<=[.!?])\s+", b)
        for i, s in enumerate(sents):
            units.append(s + (" " if i < len(sents) - 1 else ""))
        units.append("\n")
    for u in units:
        if u == "\n":
            if buf:
                parts.append(buf)
                buf = ""
            if parts and not parts[-1].endswith("\n"):
                parts[-1] = parts[-1] + "\n"
            continue
        if len(buf) + len(u) <= limit:
            buf += u
        else:
            if buf:
                parts.append(buf)
            if len(u) <= limit:
                buf = u
            else:
                # ตัดดิบ ๆ
                for i in range(0, len(u), limit):
                    parts.append(u[i : i + limit])
                buf = ""
    if buf:
        parts.append(buf)
    return [p for p in parts if p.strip()]


def translate_one(translator, engine: str, text: str, sleep_s: float, retries: int = 8) -> str:
    from deep_translator import GoogleTranslator, MyMemoryTranslator
    from deep_translator.exceptions import TooManyRequests

    text = text or ""
    if not text.strip():
        return text

    if engine == "translators":
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                # google / bing / alibaba — สลับเมื่อโดนบล็อก
                backends = ("google", "bing", "alibaba")
                backend = backends[attempt % len(backends)]
                piece = translator.translate_text(
                    text, translator=backend, from_language="en", to_language="th"
                )
                time.sleep(sleep_s)
                return piece or ""
            except Exception as e:
                last_err = e
                wait = sleep_s * (attempt + 3) + 2
                print("  rate-limit (translators/%s) sleep %.1fs" % (backend, wait))
                time.sleep(wait)
        print("  soft 90s หลัง translators หมด retry…")
        time.sleep(90)
        try:
            return translator.translate_text(
                text, translator="google", from_language="en", to_language="th"
            ) or ""
        except Exception as e2:
            raise RuntimeError("แปลไม่สำเร็จ (โควต้า): %s" % (e2 or last_err))

    chunks = _chunk_text(text, 450 if engine != "google" else 4500)
    outs: list[str] = []
    for chunk in chunks:
        last_err = None
        ok = False
        for attempt in range(retries):
            try:
                piece = translator.translate(chunk)
                time.sleep(sleep_s)
                outs.append(piece or "")
                ok = True
                break
            except TooManyRequests as e:
                last_err = e
                wait = sleep_s * (attempt + 3) + 2
                print("  rate-limit (%s) sleep %.1fs" % (engine, wait))
                time.sleep(wait)
                if engine == "mymemory":
                    try:
                        translator = GoogleTranslator(source="en", target="th")
                        engine = "google"
                    except Exception:
                        pass
                else:
                    translator = MyMemoryTranslator(source="en-US", target="th-TH")
                    engine = "mymemory"
            except Exception as e:
                msg = str(e)
                last_err = e
                # ข้อความยาวเกิน — ตัดเล็กลงแล้วลองใหม่
                if "500" in msg or "length" in msg.lower():
                    sub = _chunk_text(chunk, 200)
                    if len(sub) > 1:
                        nested = translate_one(translator, engine, "\n".join(sub), sleep_s, retries)
                        outs.append(nested)
                        ok = True
                        break
                time.sleep(sleep_s * (attempt + 2) + 1)
        if not ok:
            # โควต้าเต็ม — พักยาวแล้วลองรอบสุดท้ายอีกครั้ง
            print("  soft 90s หลัง rate-limit หมด retry…")
            time.sleep(90)
            try:
                piece = translator.translate(chunk)
                time.sleep(max(sleep_s, 1.2))
                outs.append(piece or "")
                continue
            except Exception as e2:
                raise RuntimeError("แปลไม่สำเร็จ (โควต้า): %s" % (e2 or last_err))
    return "".join(outs)


def process_file(
    src: Path,
    dest: Path,
    engine: str,
    sleep_s: float,
    save_every: int,
    limit: int | None,
    cache: dict[str, str],
) -> tuple[int, int, int]:
    # ต่อจาก dest ถ้ามี
    work = dest if dest.exists() else src
    with work.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    name, translator = make_translator(engine)
    done = cached_hits = skipped = 0

    for r in rows:
        th = (r.get("TH") or "").strip()
        st = (r.get("สถานะ") or "").strip()
        en = r.get("EN") or ""
        if st in ("ok", "fix", "skip") or th:
            skipped += 1
            continue
        if not en.strip():
            skipped += 1
            continue

        if en in cache:
            r["TH"] = cache[en]
            r["สถานะ"] = "mt"
            cached_hits += 1
            done += 1
        else:
            try:
                th_new = translate_one(translator, name, en, sleep_s=sleep_s)
            except RuntimeError as e:
                _write(dest, rows)
                save_cache(cache)
                print("  STOP บันทึกแล้วที่ +%d — %s" % (done, e))
                print("  รอ 180s แล้วรันคำสั่งเดิมอีกครั้งเพื่อต่อ")
                raise
            cache[en] = th_new
            r["TH"] = th_new
            r["สถานะ"] = "mt"
            done += 1
            if done % 5 == 0 or done == 1:
                preview = en.replace("\n", " ")[:55]
                print("  [%s] +%d (cache=%d) %s" % (src.stem, done, cached_hits, preview))

        if save_every > 0 and done % save_every == 0:
            _write(dest, rows)
            save_cache(cache)
            print("  checkpoint %s (%d)" % (dest.name, done))

        if limit is not None and done >= limit:
            break

    _write(dest, rows)
    save_cache(cache)
    return done, cached_hits, skipped


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", type=Path, help="CSV ต้นทาง")
    ap.add_argument("--queue", choices=["remaining"], default=None)
    ap.add_argument(
        "--engine",
        default="translators",
        choices=["translators", "mymemory", "google", "auto"],
    )
    ap.add_argument("--sleep", type=float, default=0.35)
    ap.add_argument("--save-every", type=int, default=20)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    if args.queue == "remaining":
        files = [SHEETS / f"{n}.csv" for n in QUEUE_REMAINING]
    else:
        files = list(args.files)
    if not files:
        ap.error("ระบุไฟล์ หรือ --queue remaining")

    cache = load_cache()
    print("cache entries:", len(cache))
    total = 0
    for src in files:
        if not src.exists():
            print("MISSING", src)
            continue
        dest = args.out_dir / src.name
        print("== %s → %s" % (src.name, dest))
        d, c, s = process_file(
            src, dest, args.engine, args.sleep, args.save_every, args.limit, cache
        )
        print("   done=%d cache_hits=%d skipped=%d" % (d, c, s))
        total += d
    print("TOTAL newly filled:", total)


if __name__ == "__main__":
    main()
