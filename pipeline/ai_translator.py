#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_translator.py — Unified AI Translation Engine for ThaiFNV
Supports Local Ollama (Typhoon, Qwen) and Cloud AI APIs (Gemini, OpenAI, OpenRouter, DeepSeek).
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
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Import Glossary & System Prompt
try:
    from pipeline.fnv_glossary import FNV_TERMS, SYSTEM_PROMPT
except ImportError:
    from fnv_glossary import FNV_TERMS, SYSTEM_PROMPT

CACHE_FILE = r"D:\backup\github\ThaiFNV\extracted\_translation_cache.json"


# ==========================================
# Translation Providers
# ==========================================

class BaseProvider:
    def translate_batch(self, items: list[dict]) -> dict[int, str]:
        raise NotImplementedError


class OllamaProvider(BaseProvider):
    def __init__(self, host: str = "http://127.0.0.1:11434", model: str = "scb10x/typhoon2.1-gemma3-12b:latest"):
        self.host = host.rstrip("/")
        self.model = model

    def translate_batch(self, items: list[dict]) -> dict[int, str]:
        user_content = json.dumps({"items_to_translate": items}, ensure_ascii=False, indent=2)
        
        # Format as prompt
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Here are the items to translate into Thai (Translate ONLY the text in the 'en' field, using other fields as background context only):\n{user_content}\n\n"
            f"REMINDER: Output MUST be ONLY valid JSON matching:\n"
            f'{{"results": [{{"id": <item_id>, "th": "<translation>"}}]}}'
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,
            }
        }
        
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "")
            return _parse_json_results(content)


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    def translate_batch(self, items: list[dict]) -> dict[int, str]:
        user_content = json.dumps({"items_to_translate": items}, ensure_ascii=False, indent=2)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "parts": [{"text": f"Translate these Fallout: New Vegas items to Thai:\n{user_content}"}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cand = data.get("candidates", [])
            if not cand:
                return {}
            text = cand[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return _parse_json_results(text)


class OpenAICompatibleProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def translate_batch(self, items: list[dict]) -> dict[int, str]:
        user_content = json.dumps({"items_to_translate": items}, ensure_ascii=False, indent=2)
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Translate these Fallout: New Vegas items to Thai:\n{user_content}"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return _parse_json_results(content)


def _parse_json_results(raw_text: str) -> dict[int, str]:
    """Parse JSON output from LLM and extract id -> translation map"""
    clean = raw_text.strip()
    
    # Strip thinking blocks <think>...</think> if present
    clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()
    
    # Look for ```json ... ``` blocks
    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, flags=re.DOTALL)
    if code_match:
        clean = code_match.group(1).strip()
    else:
        # Look for innermost or outermost { ... }
        brace_match = re.search(r"(\{.*\})", clean, flags=re.DOTALL)
        if brace_match:
            clean = brace_match.group(1).strip()

    try:
        obj = json.loads(clean)
    except json.JSONDecodeError:
        # Fallback regex extraction if JSON is slightly truncated
        matches = re.findall(r'["\']?id["\']?\s*:\s*(\d+).*?["\']?th["\']?\s*:\s*["\'](.*?)["\']', clean)
        return {int(mid): mth for mid, mth in matches}

    res_map = {}
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
# Main Translation Pipeline
# ==========================================

class TranslationPipeline:
    def __init__(self, provider: BaseProvider, batch_size: int = 5, save_every: int = 20):
        self.provider = provider
        self.batch_size = batch_size
        self.save_every = save_every
        self.cache = load_cache()
        self.interrupted = False

    def handle_interrupt(self, sig, frame):
        print("\n\n[!] Interrupt signal received! Saving current progress and exiting cleanly...")
        self.interrupted = True

    def translate_file(self, csv_path: str, limit: int = 0, overwrite: bool = False):
        signal.signal(signal.SIGINT, self.handle_interrupt)

        if not os.path.exists(csv_path):
            print(f"Error: {csv_path} not found!")
            return

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        if not rows:
            print(f"File {csv_path} is empty.")
            return

        print(f"Processing: {csv_path} ({len(rows):,} total rows)")

        # Collect pending rows
        pending_indices = []
        for idx, r in enumerate(rows):
            en_text = r.get("EN", "").strip()
            if not en_text:
                continue
            th_text = r.get("TH", "").strip()
            if not overwrite and th_text:
                continue
            pending_indices.append(idx)
            if limit and len(pending_indices) >= limit:
                break

        print(f"Pending translation: {len(pending_indices):,} rows")
        if not pending_indices:
            print("All rows already translated! Nothing to do.")
            return

        translated_count = 0
        cache_hits = 0
        batch_items = []
        batch_map = {}  # local item_id -> row_idx
        local_id_counter = 1

        def save_progress():
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            save_cache(self.cache)

        t0 = time.time()

        for step, row_idx in enumerate(pending_indices, 1):
            if self.interrupted:
                break

            r = rows[row_idx]
            en = r.get("EN", "").strip()

            # Check cache first
            if en in self.cache and not overwrite:
                r["TH"] = self.cache[en]
                r["Status"] = "cache"
                cache_hits += 1
                translated_count += 1
                continue

            # Check glossary exact match
            if en in FNV_TERMS and not overwrite:
                th_term = FNV_TERMS[en]
                r["TH"] = th_term
                r["Status"] = "glossary"
                self.cache[en] = th_term
                translated_count += 1
                continue

            # Build rich context payload
            item_payload = {
                "id": local_id_counter,
                "en": en,
            }
            if r.get("Speaker"):
                item_payload["speaker"] = r["Speaker"]
            if r.get("Emotion"):
                item_payload["emotion"] = r["Emotion"]
            if r.get("ActorNotes"):
                item_payload["actor_notes"] = r["ActorNotes"]
            if r.get("Topic_Name"):
                item_payload["topic"] = r["Topic_Name"]
            if r.get("Quest_Name"):
                item_payload["quest"] = r["Quest_Name"]
            if r.get("UI_Context"):
                item_payload["context_hint"] = r["UI_Context"]
            if r.get("ItemType"):
                item_payload["item_type"] = r["ItemType"]
            if r.get("Category"):
                item_payload["category"] = r["Category"]

            batch_items.append(item_payload)
            batch_map[local_id_counter] = row_idx
            local_id_counter += 1

            # When batch is full or at the end
            if len(batch_items) >= self.batch_size or step == len(pending_indices):
                try:
                    translations = self.provider.translate_batch(batch_items)
                    for bid, th in translations.items():
                        if bid in batch_map:
                            target_idx = batch_map[bid]
                            target_row = rows[target_idx]
                            target_row["TH"] = th
                            target_row["Status"] = "ai"
                            self.cache[target_row["EN"].strip()] = th
                            translated_count += 1
                except Exception as e:
                    print(f"\n[Warning] Batch translation error: {e}")
                    time.sleep(1)

                batch_items = []
                batch_map = {}

                # Progress display
                pct = (step / len(pending_indices)) * 100
                speed = translated_count / max(0.1, time.time() - t0)
                print(f"\rProgress: {step}/{len(pending_indices)} ({pct:.1f}%) | "
                      f"Translated: {translated_count} (Cache: {cache_hits}) | "
                      f"{speed:.1f} items/s", end="", flush=True)

                if step % self.save_every == 0:
                    save_progress()

        save_progress()
        print(f"\n\nDone! Successfully updated {translated_count} rows in {csv_path} "
              f"in {time.time() - t0:.1f}s.")


# ==========================================
# CLI Entrypoint
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="ThaiFNV AI Translation Engine")
    parser.add_argument("--file", required=True, help="Path to CSV file to translate")
    parser.add_argument("--provider", choices=["ollama", "gemini", "openai"], default="ollama",
                        help="AI Provider: ollama (default), gemini, openai")
    parser.add_argument("--model", default="", help="Model name (e.g. scb10x/typhoon2.1-gemma3-12b:latest, gemini-2.5-flash)")
    parser.add_argument("--api-key", default="", help="API key for Gemini or OpenAI (or set via environment variable)")
    parser.add_argument("--base-url", default="https://api.openai.com/v1", help="Custom base URL for OpenAI-compatible API")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size per prompt (default: 5)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rows to translate (for testing)")
    parser.add_argument("--overwrite", action="store_true", help="Re-translate rows even if TH is already present")
    args = parser.parse_args()

    # Determine Provider
    if args.provider == "ollama":
        model = args.model or "scb10x/typhoon2.1-gemma3-12b:latest"
        print(f"Using Provider: Local Ollama (Model: {model})")
        provider = OllamaProvider(model=model)
    elif args.provider == "gemini":
        api_key = args.api_key or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            print("Error: Gemini API key required! Pass via --api-key or set GEMINI_API_KEY environment variable.")
            sys.exit(1)
        model = args.model or "gemini-2.5-flash"
        print(f"Using Provider: Google Gemini API (Model: {model})")
        provider = GeminiProvider(api_key=api_key, model=model)
    elif args.provider == "openai":
        api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            print("Error: OpenAI/Compatible API key required! Pass via --api-key or set OPENAI_API_KEY environment variable.")
            sys.exit(1)
        model = args.model or "gpt-4o-mini"
        print(f"Using Provider: OpenAI Compatible API (Model: {model}, Base URL: {args.base_url})")
        provider = OpenAICompatibleProvider(api_key=api_key, base_url=args.base_url, model=model)

    pipeline = TranslationPipeline(provider=provider, batch_size=args.batch_size)
    pipeline.translate_file(args.file, limit=args.limit, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
