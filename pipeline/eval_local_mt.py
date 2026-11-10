#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_local_mt.py — Evaluate local MT against corpus/gold/fnv_gold_eval.jsonl

Pass criteria (Phase A):
- glossary/must_contain miss rate < 10%
- QA fail rate < 15%
- zero corruption on gold set
- doctor/professional register fail == 0
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.ai_translator import (  # noqa: E402
    DEFAULT_OLLAMA_MODEL,
    OllamaProvider,
    enrich_item_with_register,
    translate_batch_with_qa,
)
from pipeline.fnv_glossary import (  # noqa: E402
    _has_thai_token,
    qa_check_translation,
    resolve_register,
)

DEFAULT_GOLD = ROOT / "corpus" / "gold" / "fnv_gold_eval.jsonl"


def load_gold(path: Path) -> list[dict[str, Any]]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        items.append(json.loads(line))
    return items


def _term_hit(th: str, term: str) -> bool:
    """Accept exact glossary form or close transliteration stem (len>=4)."""
    if not term:
        return True
    if term in th:
        return True
    # Allow minor vowel/spelling drift on long terms (คาซาโดเรส≈คาซาดอร์, ดิไวค์≈ดีไวด์)
    if len(term) >= 4:
        stem4 = term[:4]
        if stem4 and stem4 in th:
            return True
    return False


def glossary_expected_hits(en: str, must_contain: list[str] | None) -> list[str]:
    """Gold must_contain only — avoids false misses from overlapping glossary keys."""
    del en  # reserved for future TM checks
    return [t for t in (must_contain or []) if t]


def evaluate_model(model: str, gold: list[dict], batch_size: int = 3) -> dict[str, Any]:
    provider = OllamaProvider(model=model)
    rows_out: list[dict[str, Any]] = []

    t0 = time.time()
    for i in range(0, len(gold), batch_size):
        chunk = gold[i : i + batch_size]
        items = []
        for g in chunk:
            item = {
                "id": int(g["id"]),
                "en": g["en"],
            }
            if g.get("speaker"):
                item["speaker"] = g["speaker"]
            if g.get("emotion"):
                item["emotion"] = g["emotion"]
            items.append(enrich_item_with_register(item))

        accepted, unresolved = translate_batch_with_qa(provider, items, max_retries=1)

        for g in chunk:
            gid = int(g["id"])
            th = accepted.get(gid, "")
            expected_reg = g.get("expected_register") or resolve_register(
                speaker=g.get("speaker") or ""
            )["key"]
            qa_fails = qa_check_translation(th, en=g["en"], register_key=expected_reg)
            if gid in unresolved:
                for f in unresolved[gid]:
                    if f not in qa_fails:
                        qa_fails.append(f)

            must = glossary_expected_hits(g["en"], g.get("must_contain"))
            missing = [t for t in must if not _term_hit(th, t)]

            # Doctor/military/robot: forbidden pronouns as whole tokens only
            reg_fail = any(f.startswith("register_forbid:") for f in qa_fails)
            if expected_reg in ("doctor", "military", "robot"):
                for tok in ("แก", "มึง", "กู"):
                    if _has_thai_token(th, tok):
                        reg_fail = True
                        tag = f"register_forbid:{tok}"
                        if tag not in qa_fails:
                            qa_fails.append(tag)

            rows_out.append(
                {
                    "id": gid,
                    "speaker": g.get("speaker"),
                    "expected_register": expected_reg,
                    "en": g["en"],
                    "gold_th": g.get("th"),
                    "pred_th": th,
                    "qa_fails": qa_fails,
                    "missing_terms": missing,
                    "register_fail": reg_fail,
                    "corruption": any(f == "corruption" for f in qa_fails),
                }
            )
            status = "OK" if not qa_fails and not missing and not reg_fail else "FAIL"
            print(f"[{status}] id={gid} reg={expected_reg} qa={qa_fails or '-'} miss={missing or '-'}")
            if th:
                print(f"       TH: {th[:120]}")

    n = len(rows_out) or 1
    qa_fail_n = sum(1 for r in rows_out if r["qa_fails"])
    gloss_miss_n = sum(1 for r in rows_out if r["missing_terms"])
    corruption_n = sum(1 for r in rows_out if r["corruption"])
    doctor_rows = [r for r in rows_out if r["expected_register"] == "doctor"]
    doctor_reg_fail = sum(1 for r in doctor_rows if r["register_fail"])
    professional_reg_fail = sum(
        1 for r in rows_out if r["expected_register"] in ("doctor", "military", "robot") and r["register_fail"]
    )

    summary = {
        "model": model,
        "n": len(rows_out),
        "elapsed_s": round(time.time() - t0, 1),
        "qa_fail_rate": qa_fail_n / n,
        "glossary_miss_rate": gloss_miss_n / n,
        "corruption_count": corruption_n,
        "doctor_register_fail": doctor_reg_fail,
        "professional_register_fail": professional_reg_fail,
        "qa_fail_n": qa_fail_n,
        "glossary_miss_n": gloss_miss_n,
    }

    # Pass criteria
    summary["pass"] = (
        summary["glossary_miss_rate"] < 0.10
        and summary["qa_fail_rate"] < 0.15
        and summary["corruption_count"] == 0
        and summary["doctor_register_fail"] == 0
        and summary["professional_register_fail"] == 0
    )
    summary["rows"] = rows_out
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    print("\n========== EVAL SUMMARY ==========")
    print(f"model: {summary['model']}")
    print(f"n: {summary['n']}  elapsed: {summary['elapsed_s']}s")
    print(f"glossary_miss_rate: {summary['glossary_miss_rate']:.1%} ({summary['glossary_miss_n']})")
    print(f"qa_fail_rate: {summary['qa_fail_rate']:.1%} ({summary['qa_fail_n']})")
    print(f"corruption_count: {summary['corruption_count']}")
    print(f"doctor_register_fail: {summary['doctor_register_fail']}")
    print(f"professional_register_fail: {summary['professional_register_fail']}")
    print(f"PASS: {summary['pass']}")
    print("Criteria: gloss<10%, qa<15%, corruption=0, doctor/pro register fail=0")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ThaiFNV local MT")
    parser.add_argument("--gold", default=str(DEFAULT_GOLD), help="Path to gold JSONL")
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Ollama model (repeatable). Default: thaifnv-typhoon",
    )
    parser.add_argument("--batch-size", type=int, default=3)
    parser.add_argument(
        "--out",
        default=str(ROOT / "corpus" / "gold" / "last_eval_report.json"),
        help="Write full JSON report",
    )
    args = parser.parse_args()

    models = args.model or [DEFAULT_OLLAMA_MODEL]
    gold = load_gold(Path(args.gold))
    print(f"Loaded {len(gold)} gold items from {args.gold}")

    reports = []
    any_pass = False
    for model in models:
        print(f"\n--- Evaluating {model} ---")
        summary = evaluate_model(model, gold, batch_size=args.batch_size)
        print_summary(summary)
        reports.append({k: v for k, v in summary.items() if k != "rows"} | {"rows": summary["rows"]})
        any_pass = any_pass or summary["pass"]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote report: {out_path}")

    sys.exit(0 if any_pass else 2)


if __name__ == "__main__":
    main()
