#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thai_wordbreak.py — แทรกช่องว่าง ASCII ที่ขอบคำไทย เพื่อให้เกมตัดบรรทัดได้

FNV ตัดบรรทัดที่ช่องว่าง และใส่ '-' กลาง "คำ" ที่ยาวไม่มีวรรค
CP874 ไม่มี ZWSP → ใช้ช่องว่างจริง (เห็นวรรคในเกมเล็กน้อย)

โหมด:
  sparse (default) — แทรกวรรคเมื่อรันไทยยาวเกิน --limit ตัวอักษร (ที่ขอบคำ)
  dense — วรรคระหว่างทุกคำจากพจนานุกรม

Usage:
  python thai_wordbreak.py "ดูเหมือนว่า...เปลี่ยนได้..."
  python thai_wordbreak.py --dense "..."
"""
from __future__ import annotations
import argparse
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# คำทับศัพท์ / คำเกมที่ newmm มักหั่นผิด
GAME_WORDS = {
    "เซอร์โว", "ไจโรสโคป", "ชิ้นส่วน", "เศษชิ้นส่วน", "เศษโลหะ",
    "อิเล็กทรอนิกส์", "เซ็นเซอร์", "โมดูล", "ดูเหมือนว่า",
    "หุ่นยนต์", "เสียหาย", "ถูกต้อง", "บางส่วน", "เปลี่ยน",
    "สามารถ", "วิทยาศาสตร์", "ซ่อมแซม", "อุปกรณ์", "อิเล็กทรอนิกส์",
    "เพื่อนร่วมงาน", "การเลิกจ้าง", "หนังสือแจ้ง",
}

_THAI_RE = re.compile(r"[\u0e00-\u0e7f]+")
_TOKENIZER = None


def _tokenizer():
    global _TOKENIZER
    if _TOKENIZER is not None:
        return _TOKENIZER
    from pythainlp.corpus.common import thai_words
    from pythainlp.tokenize import Tokenizer
    from pythainlp.util import dict_trie
    words = set(thai_words()).union(GAME_WORDS)
    _TOKENIZER = Tokenizer(custom_dict=dict_trie(words), engine="newmm")
    return _TOKENIZER


def tokenize(text: str) -> list[str]:
    """ตัดคำ คงช่องว่างเดิมเป็น token"""
    return _tokenizer().word_tokenize(text)


def insert_word_spaces(text: str, mode: str = "sparse", limit: int = 28) -> str:
    """แทรก ' ' ที่ขอบคำไทย

    sparse: เมื่อรันอักษรไทยติดกันยาว >= limit ให้ใส่วรรคที่ขอบคำถัดไป
    dense: วรรคระหว่างทุกคำ (ยกเว้นวรรคควบเครื่องหมาย)
    """
    if not text or not _THAI_RE.search(text):
        return text
    tokens = tokenize(text)
    if mode == "dense":
        return _join_dense(tokens)
    return _join_sparse(tokens, limit)


def _is_thai_token(t: str) -> bool:
    return bool(t) and bool(_THAI_RE.fullmatch(t))


def _join_dense(tokens: list[str]) -> str:
    nospace_before = set("),.;:]!?>%")
    nospace_after = set("([<\"'")
    out: list[str] = []
    for t in tokens:
        if t.isspace():
            if out and not out[-1].endswith(" "):
                out.append(" ")
            continue
        if not out:
            out.append(t)
            continue
        prev = out[-1]
        if t in nospace_before or prev[-1:] in nospace_after:
            out.append(t)
        elif prev.endswith(" ") or t.startswith(" "):
            out.append(t.lstrip() if prev.endswith(" ") else t)
        else:
            out.append(" " + t)
    s = "".join(out)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+([)\],.;:!?])", r"\1", s)
    s = re.sub(r"([(\[])\s+", r"\1", s)
    return s.strip()


def _join_sparse(tokens: list[str], limit: int) -> str:
    """คงข้อความเดิม ส่วนใหญ่ — แทรก ' ' เฉพาะเมื่อรันไทยยาวเกิน limit"""
    out: list[str] = []
    run = 0  # ความยาวอักษรไทยติดกันตั้งแต่วรรค/เครื่องหมายล่าสุด
    for t in tokens:
        if t.isspace():
            out.append(" ")
            run = 0
            continue
        if _is_thai_token(t):
            if run >= limit and out and not str(out[-1]).endswith(" "):
                out.append(" ")
                run = 0
            out.append(t)
            run += len(t)
        else:
            out.append(t)
            # ช่องว่างที่มีอยู่แล้ว / ละติน / เลข / วรรคตอน → รีเซ็ต run
            if t.strip() == "" or re.search(r"[A-Za-z0-9\(\)\[\]\s]", t):
                run = 0
    s = "".join(out)
    s = re.sub(r"\s{2,}", " ", s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?")
    ap.add_argument("--dense", action="store_true")
    ap.add_argument("--limit", type=int, default=28)
    ap.add_argument("--file", help="อ่านข้อความจากไฟล์ utf-8")
    args = ap.parse_args()
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read().rstrip("\n")
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read().rstrip("\n")
    mode = "dense" if args.dense else "sparse"
    out = insert_word_spaces(text, mode=mode, limit=args.limit)
    print(out)
    if out != text:
        print("---", file=sys.stderr)
        print("in : %d chars, out: %d chars (+%d spaces)" % (
            len(text), len(out), out.count(" ") - text.count(" ")), file=sys.stderr)


if __name__ == "__main__":
    main()
