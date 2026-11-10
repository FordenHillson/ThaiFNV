#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_translator.py — Unified AI Translation Engine for ThaiFNV
Supports Local Ollama (thaifnv-typhoon / Typhoon / Qwen) and Cloud AI APIs.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

_API_EXECUTOR = ThreadPoolExecutor(max_workers=4)
API_CALL_TIMEOUT_SEC = 90

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from pipeline.fnv_glossary import (
        FNV_TERMS,
        SYSTEM_PROMPT,
        format_glossary_block,
        match_glossary_terms,
        qa_check_translation,
        resolve_register,
    )
except ImportError:
    from fnv_glossary import (
        FNV_TERMS,
        SYSTEM_PROMPT,
        format_glossary_block,
        match_glossary_terms,
        qa_check_translation,
        resolve_register,
    )

CACHE_FILE = r"D:\backup\github\ThaiFNV\extracted\_translation_cache.json"
DEFAULT_OLLAMA_MODEL = "thaifnv-typhoon"
QA_MAX_RETRIES = 2


class FatalProviderError(RuntimeError):
    """Non-retryable provider failure (quota/credits, auth, billing). Stop the job."""

    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


_QUOTA_MARKERS = (
    "insufficient",
    "insufficient_quota",
    "quota",
    "balance",
    "billing",
    "payment required",
    "payment_required",
    "credit",
    "credits",
    "exhausted",
    "exceeded your current quota",
    "out of",
    "arrear",
    "top up",
    "top-up",
    "topup",
    "prepaid",
    "please recharge",
    "recharge",
    "account has no",
    "no remaining",
)


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _is_quota_or_auth_failure(status: int | None, body: str) -> bool:
    if status in (401, 402):
        return True
    text = (body or "").lower()
    if any(m in text for m in _QUOTA_MARKERS):
        return True
    # 403/429 with quota wording already covered; bare 403 often means bad key/plan
    if status == 403 and ("key" in text or "auth" in text or "permission" in text or "forbidden" in text):
        return True
    return False


def _raise_for_provider_http_error(exc: urllib.error.HTTPError, provider_label: str) -> None:
    body = _read_http_error_body(exc)
    status = getattr(exc, "code", None)
    if _is_quota_or_auth_failure(status, body):
        detail = body.strip()[:300] if body.strip() else (exc.reason or "quota/auth error")
        raise FatalProviderError(
            f"{provider_label}: เครดิต/โควต้าหมดหรือ API key ใช้ไม่ได้ (HTTP {status}): {detail}",
            status=status,
            body=body,
        ) from exc
    detail = body.strip()[:300] if body.strip() else str(exc.reason or exc)
    raise RuntimeError(f"{provider_label} HTTP {status}: {detail}") from exc


# ==========================================
# Prompt helpers
# ==========================================

def _build_user_prompt(items: list[dict], glossary: dict[str, str] | None = None) -> str:
    gloss = glossary if glossary is not None else match_glossary_terms(
        [str(it.get("en", "")) for it in items]
    )
    payload = {"items_to_translate": items}
    return (
        "Translate ONLY the text in each item's 'en' field into Thai. "
        "Other fields (speaker, emotion, actor_notes, topic, quest, register) are context.\n\n"
        f"BATCH GLOSSARY (use these locked Thai forms):\n{format_glossary_block(gloss)}\n\n"
        f"ITEMS:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        'Return ONLY JSON: {"results": [{"id": <id>, "th": "<thai>"}]}'
    )


def enrich_item_with_register(item: dict) -> dict:
    """Attach register hint from speaker context."""
    out = dict(item)
    reg = resolve_register(
        speaker=str(out.get("speaker") or ""),
        emotion=str(out.get("emotion") or ""),
        actor_notes=str(out.get("actor_notes") or ""),
        category=str(out.get("category") or ""),
        context_hint=str(out.get("context_hint") or ""),
    )
    out["register"] = reg["hint"]
    out["register_key"] = reg["key"]
    return out


# ==========================================
# Translation Providers
# ==========================================

class BaseProvider:
    def translate_batch(self, items: list[dict]) -> dict[int, str]:
        raise NotImplementedError


class OllamaProvider(BaseProvider):
    def __init__(self, host: str = "http://127.0.0.1:11434", model: str = DEFAULT_OLLAMA_MODEL):
        self.host = host.rstrip("/")
        self.model = model

    def translate_batch(self, items: list[dict]) -> dict[int, str]:
        user_content = _build_user_prompt(items)
        # Note: Typhoon/Gemma via Ollama rejects format="json" (sampler init 400).
        # Rely on SYSTEM_PROMPT + parser instead.
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "options": {
                "temperature": 0.15,
                "top_p": 0.9,
            },
        }

        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "")
            return _parse_json_results(content)


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    def translate_batch(self, items: list[dict]) -> dict[int, str]:
        user_content = _build_user_prompt(items)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": user_content}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.15,
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            _raise_for_provider_http_error(e, "Gemini")
        cand = data.get("candidates", [])
        if not cand:
            return {}
        text = cand[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return _parse_json_results(text)


class OpenAICompatibleProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.last_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self.usage_total: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def translate_batch(self, items: list[dict]) -> dict[int, str]:
        user_content = _build_user_prompt(items)
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.15,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        label = "DeepSeek" if "deepseek" in self.base_url.lower() else "OpenAI-compatible"

        def _do_request() -> dict:
            with urllib.request.urlopen(req, timeout=API_CALL_TIMEOUT_SEC) as resp:
                return json.loads(resp.read().decode("utf-8"))

        try:
            data = _API_EXECUTOR.submit(_do_request).result(timeout=API_CALL_TIMEOUT_SEC + 5)
        except FuturesTimeout as e:
            raise TimeoutError(f"{label}: API timeout {API_CALL_TIMEOUT_SEC}s") from e
        except urllib.error.HTTPError as e:
            _raise_for_provider_http_error(e, label)
        usage = data.get("usage") or {}
        self.last_usage = {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
        if not self.last_usage["total_tokens"]:
            self.last_usage["total_tokens"] = (
                self.last_usage["prompt_tokens"] + self.last_usage["completion_tokens"]
            )
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            self.usage_total[key] = int(self.usage_total.get(key, 0)) + self.last_usage[key]
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _parse_json_results(content)


def fetch_deepseek_balance(api_key: str) -> dict[str, Any]:
    """Query DeepSeek /user/balance. Returns money balance (not raw token quota)."""
    req = urllib.request.Request(
        "https://api.deepseek.com/user/balance",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _raise_for_provider_http_error(e, "DeepSeek")

    infos = data.get("balance_infos") or []
    # Prefer USD when multiple currencies exist
    chosen = None
    for info in infos:
        if str(info.get("currency", "")).upper() == "USD":
            chosen = info
            break
    if chosen is None and infos:
        chosen = infos[0]
    if not chosen:
        return {
            "ok": False,
            "error": "ไม่พบข้อมูลยอดคงเหลือจาก DeepSeek",
            "raw": data,
        }

    def _num(v: Any) -> float:
        try:
            s = str(v).strip()
            if not s or s == "-":
                return 0.0
            return float(s)
        except Exception:
            return 0.0

    currency = str(chosen.get("currency") or "USD")
    total = _num(chosen.get("total_balance"))
    granted = _num(chosen.get("granted_balance"))
    topped = _num(chosen.get("topped_up_balance"))

    # Blended $/1M tokens for this app (~85% input / 15% output, flash off-peak)
    input_per_m = 0.15
    output_per_m = 0.60
    blended_per_m = input_per_m * 0.85 + output_per_m * 0.15
    est_tokens = int(total / blended_per_m * 1_000_000) if blended_per_m > 0 else 0

    return {
        "ok": True,
        "is_available": bool(data.get("is_available", True)),
        "currency": currency,
        "total_balance": total,
        "granted_balance": granted,
        "topped_up_balance": topped,
        "est_tokens_remaining": est_tokens,
        "blended_usd_per_mtok": round(blended_per_m, 4),
        "note": "DeepSeek ให้ยอดเงิน ไม่ใช่โควต้า token — ตัวเลข token เป็นประมาณการจากราคาแปล",
        "raw": data,
    }


def _parse_json_results(raw_text: str) -> dict[int, str]:
    """Parse JSON output from LLM and extract id -> translation map"""
    clean = (raw_text or "").strip()

    clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()

    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, flags=re.DOTALL)
    if code_match:
        clean = code_match.group(1).strip()
    else:
        brace_match = re.search(r"(\{.*\})", clean, flags=re.DOTALL)
        if brace_match:
            clean = brace_match.group(1).strip()

    try:
        obj = json.loads(clean)
    except json.JSONDecodeError:
        matches = re.findall(
            r'["\']?id["\']?\s*:\s*(\d+).*?["\']?th["\']?\s*:\s*["\'](.*?)["\']',
            clean,
            flags=re.DOTALL,
        )
        return {int(mid): mth for mid, mth in matches}

    res_map: dict[int, str] = {}
    items = obj.get("results") or obj.get("translations") or obj.get("items") or []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and "id" in item and "th" in item:
                try:
                    res_map[int(item["id"])] = str(item["th"]).strip()
                except (ValueError, TypeError):
                    continue
    elif isinstance(items, dict):
        for k, v in items.items():
            try:
                res_map[int(k)] = str(v).strip()
            except (ValueError, TypeError):
                continue
    return res_map


# ==========================================
# Cache Management
# ==========================================

def load_cache() -> dict[str, str]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict[str, str]):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ==========================================
# QA + retry
# ==========================================

def translate_batch_with_qa(
    provider: BaseProvider,
    items: list[dict],
    max_retries: int = QA_MAX_RETRIES,
) -> tuple[dict[int, str], dict[int, list[str]]]:
    """
    Translate a batch, QA each item, retry failures individually.
    Returns (id->th, id->fail_reasons for unresolved).
    """
    enriched = [enrich_item_with_register(it) for it in items]
    id_to_meta = {int(it["id"]): it for it in enriched}

    try:
        results = provider.translate_batch(enriched)
    except FatalProviderError:
        raise
    except TimeoutError:
        raise
    except Exception as e:
        print(f"\n[Warning] Batch error: {e}")
        results = {}

    accepted: dict[int, str] = {}
    pending_fail: dict[int, list[str]] = {}

    for iid, meta in id_to_meta.items():
        th = results.get(iid, "")
        fails = qa_check_translation(
            th,
            en=str(meta.get("en") or ""),
            register_key=str(meta.get("register_key") or "default"),
        )
        if not fails:
            accepted[iid] = th
        else:
            pending_fail[iid] = fails

    for attempt in range(1, max_retries + 1):
        if not pending_fail:
            break
        still: dict[int, list[str]] = {}
        for iid, fails in list(pending_fail.items()):
            meta = dict(id_to_meta[iid])
            meta["id"] = 1
            meta["qa_retry"] = (
                f"Previous output failed QA: {', '.join(fails)}. "
                f"Fix register/pronouns. {meta.get('register', '')}"
            )
            try:
                retry_map = provider.translate_batch([meta])
                th = retry_map.get(1, "")
            except FatalProviderError:
                raise
            except TimeoutError:
                raise
            except Exception as e:
                print(f"\n[Warning] Retry error id={iid}: {e}")
                th = ""
            new_fails = qa_check_translation(
                th,
                en=str(meta.get("en") or ""),
                register_key=str(meta.get("register_key") or "default"),
            )
            if th and not new_fails:
                accepted[iid] = th
            elif th and attempt == max_retries:
                # Keep draft for human review
                accepted[iid] = th
                still[iid] = new_fails or ["empty"]
            else:
                still[iid] = new_fails or ["empty"]
        pending_fail = still

    unresolved = dict(pending_fail)
    return accepted, unresolved


# ==========================================
# Main Translation Pipeline
# ==========================================

class TranslationPipeline:
    def __init__(self, provider: BaseProvider, batch_size: int = 3, save_every: int = 20):
        self.provider = provider
        self.batch_size = batch_size
        self.save_every = save_every
        self.cache = load_cache()
        self.interrupted = False

    def handle_interrupt(self, sig, frame):
        print("\n\n[!] Interrupt signal received! Saving current progress and exiting cleanly...")
        self.interrupted = True

    def _status_field(self, fieldnames: list[str]) -> str:
        if "Status" in fieldnames:
            return "Status"
        if "สถานะ" in fieldnames:
            return "สถานะ"
        return "Status"

    def _build_item(self, local_id: int, r: dict) -> dict:
        item: dict[str, Any] = {"id": local_id, "en": (r.get("EN") or "").strip()}
        # Required context when columns exist
        for src, dst in (
            ("Speaker", "speaker"),
            ("Emotion", "emotion"),
            ("ActorNotes", "actor_notes"),
            ("Topic_Name", "topic"),
            ("Quest_Name", "quest"),
            ("UI_Context", "context_hint"),
            ("ItemType", "item_type"),
            ("Category", "category"),
        ):
            val = (r.get(src) or "").strip()
            if val:
                item[dst] = val
        return enrich_item_with_register(item)

    def translate_file(self, csv_path: str, limit: int = 0, overwrite: bool = False):
        signal.signal(signal.SIGINT, self.handle_interrupt)

        if not os.path.exists(csv_path):
            print(f"Error: {csv_path} not found!")
            return

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        if not rows:
            print(f"File {csv_path} is empty.")
            return

        status_col = self._status_field(fieldnames)
        if status_col not in fieldnames:
            fieldnames.append(status_col)

        print(f"Processing: {csv_path} ({len(rows):,} total rows)")

        pending_indices: list[int] = []
        for idx, r in enumerate(rows):
            en_text = (r.get("EN") or "").strip()
            if not en_text:
                continue
            th_text = (r.get("TH") or "").strip()
            if not overwrite and th_text:
                continue
            pending_indices.append(idx)
            if limit and len(pending_indices) >= limit:
                break

        # Group dialogue-like rows by Speaker so a batch does not mix registers
        has_speaker = any((rows[i].get("Speaker") or "").strip() for i in pending_indices)
        if has_speaker:
            pending_indices.sort(
                key=lambda i: (
                    (rows[i].get("Speaker") or "").strip().lower(),
                    i,
                )
            )

        print(f"Pending translation: {len(pending_indices):,} rows")
        if not pending_indices:
            print("All rows already translated! Nothing to do.")
            return

        translated_count = 0
        cache_hits = 0
        needs_review = 0

        def save_progress():
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            save_cache(self.cache)

        t0 = time.time()
        batch_items: list[dict] = []
        batch_map: dict[int, int] = {}
        local_id_counter = 1
        batch_speaker: str | None = None

        def flush_batch():
            nonlocal batch_items, batch_map, local_id_counter, translated_count, needs_review, batch_speaker
            if not batch_items:
                return
            try:
                accepted, unresolved = translate_batch_with_qa(self.provider, batch_items)
            except FatalProviderError as e:
                print(f"\n[Fatal] หยุดงานอัตโนมัติ: {e}")
                self.interrupted = True
                batch_items = []
                batch_map = {}
                batch_speaker = None
                return
            for bid, th in accepted.items():
                if bid not in batch_map:
                    continue
                target_row = rows[batch_map[bid]]
                target_row["TH"] = th
                if bid in unresolved:
                    target_row[status_col] = "needs_review"
                    needs_review += 1
                else:
                    target_row[status_col] = "ai"
                    self.cache[target_row["EN"].strip()] = th
                translated_count += 1
            # missing ids entirely
            for bid, row_idx in batch_map.items():
                if bid not in accepted:
                    rows[row_idx][status_col] = "needs_review"
                    needs_review += 1
            batch_items = []
            batch_map = {}
            batch_speaker = None

        for step, row_idx in enumerate(pending_indices, 1):
            if self.interrupted:
                break

            r = rows[row_idx]
            en = (r.get("EN") or "").strip()

            if en in self.cache and not overwrite:
                r["TH"] = self.cache[en]
                r[status_col] = "cache"
                cache_hits += 1
                translated_count += 1
                continue

            if en in FNV_TERMS and not overwrite:
                th_term = FNV_TERMS[en]
                r["TH"] = th_term
                r[status_col] = "glossary"
                self.cache[en] = th_term
                translated_count += 1
                continue

            speaker = (r.get("Speaker") or "").strip()
            # Start new batch if speaker changes (when grouping)
            if (
                has_speaker
                and batch_items
                and batch_speaker is not None
                and speaker != batch_speaker
            ):
                flush_batch()

            item_payload = self._build_item(local_id_counter, r)
            batch_items.append(item_payload)
            batch_map[local_id_counter] = row_idx
            local_id_counter += 1
            if batch_speaker is None:
                batch_speaker = speaker

            if len(batch_items) >= self.batch_size or step == len(pending_indices):
                flush_batch()

                pct = (step / len(pending_indices)) * 100
                speed = translated_count / max(0.1, time.time() - t0)
                print(
                    f"\rProgress: {step}/{len(pending_indices)} ({pct:.1f}%) | "
                    f"Translated: {translated_count} (Cache: {cache_hits}, Review: {needs_review}) | "
                    f"{speed:.1f} items/s",
                    end="",
                    flush=True,
                )

                if step % self.save_every == 0:
                    save_progress()

        flush_batch()
        save_progress()
        print(
            f"\n\nDone! Updated {translated_count} rows in {csv_path} "
            f"in {time.time() - t0:.1f}s (needs_review={needs_review})."
        )


# ==========================================
# CLI Entrypoint
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="ThaiFNV AI Translation Engine")
    parser.add_argument("--file", required=True, help="Path to CSV file to translate")
    parser.add_argument(
        "--provider",
        choices=["ollama", "gemini", "openai"],
        default="ollama",
        help="AI Provider: ollama (default), gemini, openai",
    )
    parser.add_argument("--model", default="", help="Model name (default ollama: thaifnv-typhoon)")
    parser.add_argument("--api-key", default="", help="API key for Gemini or OpenAI")
    parser.add_argument(
        "--base-url",
        default="https://api.openai.com/v1",
        help="Custom base URL for OpenAI-compatible API",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Batch size per prompt (default: 3 for dialogue)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit rows to translate")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-translate rows even if TH is already present",
    )
    args = parser.parse_args()

    if args.provider == "ollama":
        model = args.model or DEFAULT_OLLAMA_MODEL
        print(f"Using Provider: Local Ollama (Model: {model})")
        provider: BaseProvider = OllamaProvider(model=model)
    elif args.provider == "gemini":
        api_key = args.api_key or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            print("Error: Gemini API key required!")
            sys.exit(1)
        model = args.model or "gemini-2.5-flash"
        print(f"Using Provider: Google Gemini API (Model: {model})")
        provider = GeminiProvider(api_key=api_key, model=model)
    else:
        api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            print("Error: OpenAI/Compatible API key required!")
            sys.exit(1)
        model = args.model or "gpt-4o-mini"
        print(f"Using Provider: OpenAI Compatible API (Model: {model}, Base URL: {args.base_url})")
        provider = OpenAICompatibleProvider(
            api_key=api_key, base_url=args.base_url, model=model
        )

    pipeline = TranslationPipeline(provider=provider, batch_size=args.batch_size)
    pipeline.translate_file(args.file, limit=args.limit, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
