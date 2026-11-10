#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_web_app.py — ThaiFNV Translation Studio Web Application
A standalone local web app for translating Fallout: New Vegas text files
using Local Ollama models (Typhoon 2.1, Qwen) or Cloud AI APIs (Gemini, OpenAI, DeepSeek).
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template_string, request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Import Glossary & Provider definitions
try:
    from pipeline.fnv_glossary import FNV_TERMS, SYSTEM_PROMPT
    from pipeline.ai_translator import (
        BaseProvider,
        FatalProviderError,
        GeminiProvider,
        OllamaProvider,
        OpenAICompatibleProvider,
        enrich_item_with_register,
        fetch_deepseek_balance,
        load_cache,
        save_cache,
        translate_batch_with_qa,
    )
except ImportError:
    from fnv_glossary import FNV_TERMS, SYSTEM_PROMPT
    from ai_translator import (
        BaseProvider,
        FatalProviderError,
        GeminiProvider,
        OllamaProvider,
        OpenAICompatibleProvider,
        enrich_item_with_register,
        fetch_deepseek_balance,
        load_cache,
        save_cache,
        translate_batch_with_qa,
    )

ROOT_DIR = Path(__file__).resolve().parents[1]
EXTRACTED_DIR = ROOT_DIR / "extracted"
BY_CATEGORY_DIR = EXTRACTED_DIR / "by_category"
BY_DLC_DIR = EXTRACTED_DIR / "by_dlc"
PORT = int(os.environ.get("PORT", "8765"))

app = Flask(__name__)


# ==============================================================================
# Job State & Thread-Safe Background Worker
# ==============================================================================

@dataclass
class JobState:
    state: str  # IDLE, RUNNING, PAUSED, FINISHED, ERROR, STOPPED
    file_path: str
    file_name: str
    provider_type: str
    model_name: str
    current_index: int
    total_target: int
    translated_count: int
    cache_hits: int
    start_time: float
    speed_per_sec: float
    live_feed: Optional[dict]
    error_msg: str
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_total: int = 0
    last_progress_at: float = 0.0
    stall_count: int = 0


class TranslationJobManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.pause_event.set()
        self.worker_thread: Optional[threading.Thread] = None
        self.state = JobState(
            state="IDLE",
            file_path="",
            file_name="",
            provider_type="",
            model_name="",
            current_index=0,
            total_target=0,
            translated_count=0,
            cache_hits=0,
            start_time=0.0,
            speed_per_sec=0.0,
            live_feed=None,
            error_msg="",
            tokens_in=0,
            tokens_out=0,
            tokens_total=0,
            last_progress_at=0.0,
            stall_count=0,
        )

    def get_status(self) -> dict:
        with self.lock:
            d = asdict(self.state)
            now = time.time()
            if self.state.state in ("RUNNING", "PAUSED") and self.state.start_time > 0:
                elapsed = max(0.1, now - self.state.start_time)
                d["elapsed_sec"] = round(elapsed, 1)
                speed = self.state.translated_count / elapsed
                d["speed_per_sec"] = round(speed, 2)
                rem = max(0, self.state.total_target - self.state.current_index)
                d["eta_sec"] = round(rem / speed, 1) if speed > 0 else 0
                stuck_for = now - (self.state.last_progress_at or self.state.start_time)
                d["stuck_for_sec"] = round(max(0.0, stuck_for), 1)
                d["is_stuck"] = self.state.state == "RUNNING" and stuck_for >= 90
            else:
                d["elapsed_sec"] = 0
                d["eta_sec"] = 0
                d["stuck_for_sec"] = 0
                d["is_stuck"] = False
            alive = bool(self.worker_thread and self.worker_thread.is_alive())
            d["worker_alive"] = alive
            if self.state.state == "RUNNING" and not alive:
                d["is_stuck"] = True
                d["error_msg"] = d.get("error_msg") or "worker thread หยุดเอง"
            return d

    def start_job(self, file_path_str: str, provider: BaseProvider, provider_type: str,
                  model_name: str, mode: str = "empty_only", batch_size: int = 3, limit: int = 0) -> dict:
        with self.lock:
            if self.state.state in ("RUNNING", "PAUSED"):
                return {"ok": False, "error": "A translation job is already in progress"}

            file_path = Path(file_path_str)
            if not file_path.exists():
                return {"ok": False, "error": f"File {file_path_str} does not exist"}

            # Load rows
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                rows = list(reader)

            if not rows:
                return {"ok": False, "error": "Selected file has no data rows"}

            # Collect target row indices
            target_indices = []
            for idx, r in enumerate(rows):
                en = (r.get("EN") or "").strip()
                if not en:
                    continue
                th = (r.get("TH") or "").strip()
                if mode == "empty_only" and th:
                    continue
                target_indices.append(idx)
                if limit and len(target_indices) >= limit:
                    break

            if not target_indices:
                return {"ok": False, "error": "No matching rows to translate (all already translated)"}

            # Group by Speaker so one batch does not mix registers
            if any((rows[i].get("Speaker") or "").strip() for i in target_indices):
                target_indices.sort(
                    key=lambda i: ((rows[i].get("Speaker") or "").strip().lower(), i)
                )

            now = time.time()
            self.state = JobState(
                state="RUNNING",
                file_path=str(file_path),
                file_name=file_path.name,
                provider_type=provider_type,
                model_name=model_name,
                current_index=0,
                total_target=len(target_indices),
                translated_count=0,
                cache_hits=0,
                start_time=now,
                speed_per_sec=0.0,
                live_feed=None,
                error_msg="",
                tokens_in=0,
                tokens_out=0,
                tokens_total=0,
                last_progress_at=now,
                stall_count=0,
            )
            self.pause_event.set()
            self.stop_event.clear()

            self.worker_thread = threading.Thread(
                target=self._run_worker,
                args=(file_path, headers, rows, target_indices, provider, batch_size),
                daemon=True,
            )
            self.worker_thread.start()
            return {"ok": True, "total": len(target_indices)}

    def pause_job(self) -> dict:
        with self.lock:
            if self.state.state != "RUNNING":
                return {"ok": False, "error": "Job is not running"}
            self.pause_event.clear()
            self.state.state = "PAUSED"
            return {"ok": True}

    def resume_job(self) -> dict:
        with self.lock:
            if self.state.state != "PAUSED":
                return {"ok": False, "error": "Job is not paused"}
            self.pause_event.set()
            self.state.state = "RUNNING"
            return {"ok": True}

    def stop_job(self) -> dict:
        with self.lock:
            self.stop_event.set()
            self.pause_event.set()
            if self.state.state in ("RUNNING", "PAUSED"):
                self.state.state = "STOPPED"
            return {"ok": True}

    def _run_worker(self, file_path: Path, headers: list[str], rows: list[dict],
                    target_indices: list[int], provider: BaseProvider, batch_size: int):
        cache = load_cache()
        save_interval = 20
        total_items = len(target_indices)
        chunk_start = 0
        local_id_counter = 1

        def touch_progress(live_feed: Optional[dict] = None):
            with self.lock:
                self.state.last_progress_at = time.time()
                if live_feed is not None:
                    self.state.live_feed = live_feed

        def save_file(make_bak: bool = False):
            touch_progress({
                "en": "",
                "th": "กำลังบันทึกไฟล์ Progressive...",
                "speaker": "",
                "source": "บันทึก",
            })
            try:
                if make_bak:
                    bak_path = file_path.with_suffix(".csv.bak")
                    shutil.copy2(file_path, bak_path)
                tmp_path = file_path.with_suffix(".csv.tmp")
                with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(rows)
                os.replace(tmp_path, file_path)
                save_cache(cache)
            except Exception as e:
                with self.lock:
                    self.state.error_msg = f"บันทึกไฟล์ไม่สำเร็จ: {e}"
                print(f"\n[Warning] save_file failed: {e}")
            finally:
                touch_progress()

        while chunk_start < total_items:
            if self.stop_event.is_set():
                break
            self.pause_event.wait()
            if self.stop_event.is_set():
                break

            chunk_indices = target_indices[chunk_start:chunk_start + batch_size]
            chunk_start += len(chunk_indices)

            batch_items = []
            batch_map = {}

            for row_idx in chunk_indices:
                r = rows[row_idx]
                en = (r.get("EN") or "").strip()

                # 1. Cache hit
                if en in cache:
                    r["TH"] = cache[en]
                    r["Status"] = "cache"
                    with self.lock:
                        self.state.cache_hits += 1
                        self.state.translated_count += 1
                        self.state.current_index += 1
                        self.state.last_progress_at = time.time()
                        self.state.live_feed = {
                            "en": en,
                            "th": cache[en],
                            "speaker": r.get("Speaker", ""),
                            "source": "Cache",
                        }
                    continue

                # 2. Glossary hit
                if en in FNV_TERMS:
                    th_term = FNV_TERMS[en]
                    r["TH"] = th_term
                    r["Status"] = "glossary"
                    cache[en] = th_term
                    with self.lock:
                        self.state.translated_count += 1
                        self.state.current_index += 1
                        self.state.last_progress_at = time.time()
                        self.state.live_feed = {
                            "en": en,
                            "th": th_term,
                            "speaker": r.get("Speaker", ""),
                            "source": "Glossary",
                        }
                    continue

                # 3. Queue for AI (with register hint)
                payload = {
                    "id": local_id_counter,
                    "en": en,
                }
                if r.get("Speaker"):
                    payload["speaker"] = r["Speaker"]
                if r.get("Emotion"):
                    payload["emotion"] = r["Emotion"]
                if r.get("ActorNotes"):
                    payload["actor_notes"] = r["ActorNotes"]
                if r.get("Topic_Name"):
                    payload["topic"] = r["Topic_Name"]
                if r.get("Quest_Name"):
                    payload["quest"] = r["Quest_Name"]
                if r.get("UI_Context"):
                    payload["context_hint"] = r["UI_Context"]
                if r.get("Category"):
                    payload["category"] = r["Category"]
                payload = enrich_item_with_register(payload)

                batch_items.append(payload)
                batch_map[local_id_counter] = row_idx
                local_id_counter += 1

            if batch_items:
                first = batch_items[0]
                touch_progress({
                    "en": str(first.get("en") or ""),
                    "th": f"กำลังเรียก AI... ({len(batch_items)} รายการใน batch นี้)",
                    "speaker": str(first.get("speaker") or ""),
                    "source": "รอ API",
                })
                try:
                    translations, unresolved = translate_batch_with_qa(provider, batch_items)
                    for bid, th in translations.items():
                        if bid in batch_map:
                            t_idx = batch_map[bid]
                            target_row = rows[t_idx]
                            target_row["TH"] = th
                            if bid in unresolved:
                                target_row["Status"] = "needs_review"
                            else:
                                target_row["Status"] = "ai"
                                cache[target_row["EN"].strip()] = th
                            with self.lock:
                                self.state.translated_count += 1
                                self.state.current_index += 1
                                self.state.last_progress_at = time.time()
                                self.state.live_feed = {
                                    "en": target_row["EN"],
                                    "th": th,
                                    "speaker": target_row.get("Speaker", ""),
                                    "source": "AI-review" if bid in unresolved else "AI",
                                }
                    # Advance index for ids missing from model response
                    for bid, row_idx in batch_map.items():
                        if bid in translations:
                            continue
                        rows[row_idx]["Status"] = "needs_review"
                        with self.lock:
                            self.state.current_index += 1
                            self.state.last_progress_at = time.time()
                            self.state.stall_count += 1
                    usage_total = getattr(provider, "usage_total", None) or {}
                    if usage_total:
                        with self.lock:
                            self.state.tokens_in = int(usage_total.get("prompt_tokens") or 0)
                            self.state.tokens_out = int(usage_total.get("completion_tokens") or 0)
                            self.state.tokens_total = int(usage_total.get("total_tokens") or 0)
                except FatalProviderError as e:
                    save_file(make_bak=True)
                    with self.lock:
                        self.state.error_msg = str(e)
                        self.state.state = "ERROR"
                    self.stop_event.set()
                    print(f"\n[Fatal] หยุดงานอัตโนมัติ: {e}")
                    return
                except (TimeoutError, urllib.error.URLError, OSError) as e:
                    # Skip this batch so a hung API call cannot freeze the whole job.
                    for row_idx in batch_map.values():
                        if not (rows[row_idx].get("TH") or "").strip():
                            rows[row_idx]["Status"] = "needs_review"
                        with self.lock:
                            self.state.current_index += 1
                            self.state.last_progress_at = time.time()
                            self.state.stall_count += 1
                    with self.lock:
                        self.state.error_msg = f"ข้าม batch เพราะ timeout/เครือข่าย: {e}"
                        self.state.live_feed = {
                            "en": str(first.get("en") or ""),
                            "th": f"ข้าม batch นี้แล้วไปต่อ: {e}",
                            "speaker": str(first.get("speaker") or ""),
                            "source": "Timeout",
                        }
                    print(f"\n[Warning] batch timeout/network, skipped: {e}")
                    time.sleep(1)
                except Exception as e:
                    with self.lock:
                        self.state.error_msg = f"ชั่วคราว: {e}"
                        self.state.last_progress_at = time.time()
                        self.state.live_feed = {
                            "en": str(first.get("en") or ""),
                            "th": f"ผิดพลาดชั่วคราว แล้วจะลองต่อ: {e}",
                            "speaker": str(first.get("speaker") or ""),
                            "source": "Error",
                        }
                    time.sleep(1)

            if self.stop_event.is_set():
                break

            if self.state.current_index > 0 and self.state.current_index % save_interval == 0:
                save_file(make_bak=(self.state.current_index % (save_interval * 5) == 0))

        save_file(make_bak=True)
        with self.lock:
            if self.state.state == "ERROR":
                return
            self.state.state = "STOPPED" if self.stop_event.is_set() else "FINISHED"


job_manager = TranslationJobManager()


# ==============================================================================
# Helper Functions: File Discovery & Metadata
# ==============================================================================

def get_available_files() -> dict:
    categories = []
    if BY_CATEGORY_DIR.exists():
        for p in sorted(BY_CATEGORY_DIR.glob("*.csv")):
            stats = get_csv_stats(p)
            categories.append({
                "name": p.name,
                "path": str(p),
                "total": stats["total"],
                "translated": stats["translated"],
                "percent": stats["percent"],
            })

    dlcs = {}
    if BY_DLC_DIR.exists():
        for dlc_folder in sorted(BY_DLC_DIR.iterdir()):
            if dlc_folder.is_dir():
                f_list = []
                for p in sorted(dlc_folder.glob("*.csv")):
                    stats = get_csv_stats(p)
                    f_list.append({
                        "name": p.name,
                        "path": str(p),
                        "total": stats["total"],
                        "translated": stats["translated"],
                        "percent": stats["percent"],
                    })
                dlcs[dlc_folder.name] = f_list

    return {"categories": categories, "dlcs": dlcs}


def get_csv_stats(path: Path) -> dict:
    total = 0
    translated = 0
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                total += 1
                if (r.get("TH") or "").strip():
                    translated += 1
    except Exception:
        pass
    pct = round((translated / max(1, total)) * 100, 1)
    return {"total": total, "translated": translated, "percent": pct}


def fetch_ollama_models(host: str = "http://127.0.0.1:11434") -> list[str]:
    try:
        req = urllib.request.Request(f"{host.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return ["thaifnv-typhoon", "scb10x/typhoon2.1-gemma3-12b:latest", "qwen3.5:9b"]


# ==============================================================================
# API Routes
# ==============================================================================

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/files")
def api_files():
    return jsonify(get_available_files())


@app.route("/api/ollama_models")
def api_ollama_models():
    host = request.args.get("host", "http://127.0.0.1:11434")
    models = fetch_ollama_models(host)
    return jsonify({"models": models})


@app.route("/api/data")
def api_data():
    file_path_str = request.args.get("file", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    filter_mode = request.args.get("filter", "all")
    search_q = request.args.get("q", "").strip().lower()

    if not file_path_str or not os.path.exists(file_path_str):
        return jsonify({"ok": False, "error": "Invalid file path"}), 400

    rows = []
    with open(file_path_str, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        for idx, r in enumerate(reader):
            r["_row_idx"] = idx
            en = (r.get("EN") or "").strip()
            th = (r.get("TH") or "").strip()

            if filter_mode == "empty" and th:
                continue
            elif filter_mode == "translated" and not th:
                continue
            elif filter_mode == "ai" and r.get("Status") != "ai":
                continue

            if search_q:
                combined = f"{en} {th} {r.get('Speaker', '')} {r.get('FormID', '')} {r.get('EditorID', '')}".lower()
                if search_q not in combined:
                    continue

            rows.append(r)

    total_count = len(rows)
    start = (page - 1) * per_page
    end = start + per_page
    page_rows = rows[start:end]

    return jsonify({
        "ok": True,
        "headers": headers,
        "rows": page_rows,
        "total": total_count,
        "page": page,
        "pages": (total_count + per_page - 1) // per_page,
    })


@app.route("/api/save_row", methods=["POST"])
def api_save_row():
    body = request.get_json() or {}
    file_path = body.get("file")
    row_idx = body.get("row_idx")
    th_val = body.get("th", "").strip()

    if not file_path or not os.path.exists(file_path) or row_idx is None:
        return jsonify({"ok": False, "error": "Invalid params"}), 400

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)

        if 0 <= row_idx < len(rows):
            rows[row_idx]["TH"] = th_val
            rows[row_idx]["Status"] = "manual"
            # save
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)

            # update cache
            cache = load_cache()
            cache[rows[row_idx]["EN"].strip()] = th_val
            save_cache(cache)
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "Index out of range"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"


def _build_provider(provider_type: str, model_name: str = "", api_key: str = "", base_url: str = ""):
    """Create AI provider from web-app settings. Returns (provider, error_message)."""
    if provider_type == "ollama":
        return OllamaProvider(model=model_name or "thaifnv-typhoon"), None
    if provider_type == "gemini":
        if not api_key:
            return None, "Gemini API Key is required"
        return GeminiProvider(api_key=api_key, model=model_name or "gemini-2.5-flash"), None
    if provider_type == "deepseek":
        if not api_key:
            return None, "DeepSeek API Key is required"
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=DEEPSEEK_BASE_URL,
            model=model_name or DEEPSEEK_DEFAULT_MODEL,
        ), None
    if provider_type == "openai":
        if not api_key:
            return None, "API Key is required"
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=(base_url or "https://api.openai.com/v1"),
            model=model_name or "gpt-4o-mini",
        ), None
    return None, "Unsupported provider"


@app.route("/api/translate_single", methods=["POST"])
def api_translate_single():
    body = request.get_json() or {}
    en_text = body.get("en", "").strip()
    provider_type = body.get("provider", "ollama")
    model_name = body.get("model", "")
    api_key = body.get("api_key", "")
    base_url = body.get("base_url", "https://api.openai.com/v1")
    speaker = body.get("speaker", "")
    emotion = body.get("emotion", "")

    if not en_text:
        return jsonify({"ok": False, "error": "Empty English text"}), 400

    provider, err = _build_provider(provider_type, model_name, api_key, base_url)
    if err:
        return jsonify({"ok": False, "error": err}), 400

    try:
        payload = [{"id": 1, "en": en_text}]
        if speaker:
            payload[0]["speaker"] = speaker
        if emotion:
            payload[0]["emotion"] = emotion
        payload[0] = enrich_item_with_register(payload[0])

        accepted, unresolved = translate_batch_with_qa(provider, payload)
        th_res = (accepted.get(1) or "").strip()
        return jsonify({
            "ok": True,
            "th": th_res,
            "needs_review": 1 in unresolved,
            "qa_fails": unresolved.get(1, []),
            "register": payload[0].get("register", ""),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _safe_int(value, default: int = 0, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        if value is None or value == "":
            n = default
        else:
            n = int(value)
    except (TypeError, ValueError):
        n = default
    if minimum is not None:
        n = max(minimum, n)
    if maximum is not None:
        n = min(maximum, n)
    return n


@app.route("/api/job/start", methods=["POST"])
def api_job_start():
    body = request.get_json() or {}
    file_path = body.get("file", "")
    provider_type = body.get("provider", "ollama")
    model_name = body.get("model", "")
    api_key = body.get("api_key", "")
    base_url = body.get("base_url", "https://api.openai.com/v1")
    mode = body.get("mode", "empty_only")
    batch_size = _safe_int(body.get("batch_size", 3), default=3, minimum=1, maximum=25)
    limit = _safe_int(body.get("limit", 0), default=0, minimum=0)

    provider, err = _build_provider(provider_type, model_name, api_key, base_url)
    if err:
        return jsonify({"ok": False, "error": err}), 400

    res = job_manager.start_job(
        file_path_str=file_path,
        provider=provider,
        provider_type=provider_type,
        model_name=model_name,
        mode=mode,
        batch_size=batch_size,
        limit=limit,
    )
    return jsonify(res)


@app.route("/api/job/status")
def api_job_status():
    return jsonify(job_manager.get_status())


@app.route("/api/job/pause", methods=["POST"])
def api_job_pause():
    return jsonify(job_manager.pause_job())


@app.route("/api/job/resume", methods=["POST"])
def api_job_resume():
    return jsonify(job_manager.resume_job())


@app.route("/api/job/stop", methods=["POST"])
def api_job_stop():
    return jsonify(job_manager.stop_job())


@app.route("/api/deepseek_balance", methods=["POST"])
def api_deepseek_balance():
    body = request.get_json() or {}
    api_key = (body.get("api_key") or "").strip()
    budget = body.get("budget_usd", None)
    if not api_key:
        return jsonify({"ok": False, "error": "ต้องใส่ DeepSeek API Key"}), 400
    try:
        bal = fetch_deepseek_balance(api_key)
    except FatalProviderError as e:
        return jsonify({"ok": False, "error": str(e)}), 402
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    if not bal.get("ok"):
        return jsonify(bal), 502

    try:
        budget_usd = float(budget) if budget not in (None, "") else None
    except (TypeError, ValueError):
        budget_usd = None

    remaining_usd = float(bal["total_balance"])
    if budget_usd is None or budget_usd <= 0:
        # fallback: use current account balance as the total pool
        budget_usd = max(remaining_usd, float(bal["granted_balance"]) + float(bal["topped_up_balance"]), 0.01)

    # Meter tracks spend against the set budget: fills as money is used.
    remaining_in_budget = max(0.0, min(remaining_usd, budget_usd))
    used_usd = max(0.0, budget_usd - remaining_in_budget)
    pct_used = max(0.0, min(100.0, (used_usd / budget_usd) * 100.0)) if budget_usd > 0 else 0.0

    bal.update({
        "budget_usd": round(budget_usd, 4),
        "remaining_usd": round(remaining_usd, 4),
        "remaining_in_budget_usd": round(remaining_in_budget, 4),
        "used_usd": round(used_usd, 4),
        "percent_used": round(pct_used, 1),
    })
    return jsonify(bal)


# ==============================================================================
# Pip-Boy Cyberpunk UI Template (Pure Offline, No CDN required)
# ==============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThaiFNV Translation Studio</title>
  <style>
    :root {
      --bg: #0d1117;
      --panel: #161b22;
      --border: #30363d;
      --accent: #22d3ee;
      --primary: #38bdf8;
      --primary-hover: #0284c7;
      --amber: #f59e0b;
      --green: #10b981;
      --red: #ef4444;
      --text: #f0f6fc;
      --text-muted: #8b949e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Sarabun", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 16px; font-size: 14px; line-height: 1.5; }

    /* Top Nav */
    .nav { display: flex; justify-content: space-between; align-items: center; background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 12px 20px; margin-bottom: 16px; }
    .brand { font-size: 18px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 10px; }
    .brand span { color: var(--amber); }

    /* Layout Grid */
    .grid { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }
    @media (max-width: 1024px) { .grid { grid-template-columns: 1fr; } }

    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 16px; }
    .card-title { font-size: 13px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }

    /* Form Controls */
    label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
    select, input[type="text"], input[type="number"], input[type="password"] {
      width: 100%; background: #090d13; border: 1px solid var(--border); border-radius: 6px; color: #fff; padding: 8px 10px; font-size: 13px; outline: none; margin-bottom: 12px;
    }
    select:focus, input:focus { border-color: var(--primary); }

    .btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: 0.15s; }
    .btn-primary { background: var(--primary); color: #000; }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-amber { background: var(--amber); color: #000; }
    .btn-amber:hover { opacity: 0.9; }
    .btn-danger { background: var(--red); color: #fff; }
    .btn-secondary { background: #21262d; color: var(--text); border: 1px solid var(--border); }
    .btn-secondary:hover { background: #30363d; }
    .btn-sm { padding: 4px 8px; font-size: 12px; }

    /* File List Tabs */
    .tab-bar { display: flex; border-bottom: 1px solid var(--border); margin-bottom: 10px; }
    .tab-btn { padding: 6px 12px; background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-weight: 600; font-size: 13px; border-bottom: 2px solid transparent; }
    .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }

    .file-list { max-height: 260px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
    .file-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; background: #0d1117; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 12px; }
    .file-item:hover { border-color: var(--primary); }
    .file-item.active { border-color: var(--amber); background: rgba(245, 158, 11, 0.08); font-weight: 600; }
    .badge { padding: 2px 6px; border-radius: 12px; font-size: 11px; background: #21262d; color: var(--text-muted); }
    .badge-amber { background: rgba(245, 158, 11, 0.15); color: var(--amber); }
    .badge-green { background: rgba(16, 185, 129, 0.15); color: var(--green); }

    /* Progress & Live Feed */
    .progress-bar-bg { width: 100%; height: 8px; background: #21262d; border-radius: 4px; overflow: hidden; margin: 8px 0; }
    .progress-bar-fill { height: 100%; background: var(--green); width: 0%; transition: width 0.3s; }
    .token-meter { margin-top: 4px; margin-bottom: 12px; padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: #090d13; }
    .token-meter-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
    .token-meter-label { font-size: 12px; color: var(--text-muted); }
    .token-meter-value { font-size: 12px; font-weight: 700; color: var(--accent); }
    .token-meter .progress-bar-bg { height: 10px; margin: 0; }
    .token-meter .progress-bar-fill.ok { background: linear-gradient(90deg, #10b981, #22d3ee); }
    .token-meter .progress-bar-fill.warn { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
    .token-meter .progress-bar-fill.low { background: linear-gradient(90deg, #ef4444, #f97316); }
    .token-meter-sub { font-size: 11px; color: var(--text-muted); margin-top: 6px; line-height: 1.4; }
    .live-feed-box { background: #090d13; border: 1px solid var(--border); border-radius: 6px; padding: 10px; font-size: 12px; min-height: 70px; }

    /* Data Table */
    .table-container { overflow: auto; max-height: calc(100vh - 180px); min-height: 520px; border: 1px solid var(--border); border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
    th { background: #1f242c; padding: 10px; position: sticky; top: 0; z-index: 10; border-bottom: 1px solid var(--border); }
    td { padding: 8px 10px; border-bottom: 1px solid #21262d; vertical-align: top; }
    tr:hover { background: rgba(56, 189, 248, 0.04); }

    textarea.edit-th { width: 100%; background: #090d13; border: 1px solid #30363d; border-radius: 4px; color: #fff; padding: 6px; font-size: 13px; resize: vertical; min-height: 44px; outline: none; }
    textarea.edit-th:focus { border-color: var(--primary); }

    .speaker-tag { display: inline-block; padding: 2px 6px; border-radius: 4px; background: #21262d; color: var(--accent); font-weight: 600; font-size: 11px; margin-bottom: 4px; }
    .notes-tag { font-size: 11px; color: var(--amber); display: block; font-style: italic; }
  </style>
</head>
<body>

  <!-- Top Navbar -->
  <div class="nav">
    <div class="brand">
      ☢️ ThaiFNV <span>Translation Studio</span>
    </div>
    <div style="display: flex; gap: 10px; align-items: center;">
      <span id="ollama-status" class="badge">Checking Ollama...</span>
      <span class="badge badge-amber">Fallout: New Vegas (Base + 9 DLCs)</span>
    </div>
  </div>

  <!-- Main Grid -->
  <div class="grid">

    <!-- Left Column: Controls & File Picker -->
    <div>

      <!-- File Browser Card -->
      <div class="card">
        <div class="card-title">
          <span>📁 เลือกไฟล์ข้อความ</span>
          <button class="btn btn-secondary btn-sm" onclick="loadFiles()">↻ รีเฟรช</button>
        </div>
        
        <div class="tab-bar">
          <button class="tab-btn active" id="tab-cat-btn" onclick="switchFileTab('cat')">แยกหมวด (Category)</button>
          <button class="tab-btn" id="tab-dlc-btn" onclick="switchFileTab('dlc')">แยก DLC</button>
        </div>

        <div id="file-list-cat" class="file-list">กำลังโหลดไฟล์...</div>
        <div id="file-list-dlc" class="file-list" style="display: none;"></div>
      </div>

      <!-- AI Provider Settings Card -->
      <div class="card">
        <div class="card-title">🤖 ตั้งค่า AI Model</div>

        <label>ผู้ให้บริการ (Provider):</label>
        <select id="provider-select" onchange="onProviderChange()">
          <option value="ollama">Local Ollama (เครื่องตัวเอง ฟรี)</option>
          <option value="deepseek">DeepSeek API</option>
          <option value="gemini">Google Gemini API</option>
          <option value="openai">OpenAI / OpenRouter (Custom)</option>
        </select>

        <div id="ollama-fields">
          <label>โมเดลในเครื่อง (Ollama Models):</label>
          <select id="ollama-model-select"></select>
        </div>

        <div id="deepseek-fields" style="display: none;">
          <label>DeepSeek API Key:</label>
          <input type="password" id="deepseek-key" placeholder="sk-...">
          <label>โมเดล (DeepSeek Model):</label>
          <select id="deepseek-model-select">
            <option value="deepseek-chat">deepseek-chat (แนะนำสำหรับแปล)</option>
            <option value="deepseek-flash">deepseek-flash</option>
            <option value="deepseek-reasoner">deepseek-reasoner</option>
          </select>
          <label>ยอดเงินที่มีทั้งหมด (USD):</label>
          <input type="number" id="deepseek-budget" value="2" min="0.01" step="0.01" placeholder="2.00">
          <div class="token-meter" id="deepseek-token-meter">
            <div class="token-meter-top">
              <span class="token-meter-label">เงินที่ใช้ไป / ทั้งหมด</span>
              <button type="button" class="btn btn-secondary btn-sm" onclick="refreshDeepseekBalance()">↻ เช็คยอด</button>
            </div>
            <div class="progress-bar-bg">
              <div id="deepseek-token-fill" class="progress-bar-fill ok" style="width: 0%"></div>
            </div>
            <div class="token-meter-top" style="margin-top: 6px; margin-bottom: 0;">
              <span class="token-meter-value" id="deepseek-token-text">ยังไม่เช็คยอด</span>
            </div>
            <div class="token-meter-sub" id="deepseek-token-sub">
              หลอดจะเพิ่มตามเงินที่ใช้ไป จนเต็มเมื่อใช้งบครบ
            </div>
          </div>
        </div>

        <div id="gemini-fields" style="display: none;">
          <label>Gemini API Key:</label>
          <input type="password" id="gemini-key" placeholder="AIzaSy...">
          <label>โมเดล (Gemini Model):</label>
          <select id="gemini-model-select">
            <option value="gemini-2.5-flash">gemini-2.5-flash (เร็วและฉลาด)</option>
            <option value="gemini-1.5-flash">gemini-1.5-flash</option>
            <option value="gemini-1.5-pro">gemini-1.5-pro</option>
          </select>
        </div>

        <div id="openai-fields" style="display: none;">
          <label>API Key:</label>
          <input type="password" id="openai-key" placeholder="sk-...">
          <label>Base URL:</label>
          <input type="text" id="openai-url" value="https://api.openai.com/v1" placeholder="https://api.openai.com/v1">
          <label>Model Name:</label>
          <input type="text" id="openai-model" value="gpt-4o-mini" placeholder="gpt-4o-mini">
        </div>

        <button id="btn-save-ai" class="btn btn-secondary btn-sm" style="margin-top: 10px;" onclick="saveProviderSettings(true)">💾 จำการตั้งค่า AI</button>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
          <div>
            <label>Batch Size:</label>
            <input type="number" id="batch-size" value="3" min="1" max="25">
          </div>
          <div>
            <label>จำกัดจำนวนแถว (Limit):</label>
            <input type="number" id="limit-rows" value="0" min="0" placeholder="0 = ทั้งหมด">
          </div>
        </div>

        <label>โหมดการแปล:</label>
        <select id="mode-select">
          <option value="empty_only">แปลเฉพาะแถวที่ยังไม่แปล (TH ว่าง)</option>
          <option value="all">แปลทั้งหมด (เขียนทับ)</option>
        </select>

        <div style="display: flex; gap: 8px; margin-top: 10px;">
          <button id="btn-start" class="btn btn-primary" style="flex: 1;" onclick="startTranslationJob()">▶ สั่งแปลไฟล์นี้</button>
          <button id="btn-pause" class="btn btn-amber" style="display: none;" onclick="pauseJob()">⏸ พัก</button>
          <button id="btn-resume" class="btn btn-amber" style="display: none;" onclick="resumeJob()">▶ ต่อ</button>
          <button id="btn-stop" class="btn btn-danger" style="display: none;" onclick="stopJob()">⏹ หยุด</button>
        </div>
      </div>

      <!-- Live Job Status Card -->
      <div id="job-card" class="card" style="display: none;">
        <div class="card-title">
          <span>⚡ สถานะการแปล</span>
          <span id="job-badge" class="badge">RUNNING</span>
        </div>
        <div class="progress-bar-bg">
          <div id="job-progress-fill" class="progress-bar-fill"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 8px;">
          <span id="job-counts">0 / 0</span>
          <span id="job-speed">0.0 รายการ/วิ</span>
        </div>
        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">
          Token ที่ใช้ในงานนี้: <span id="job-tokens" style="color: var(--accent); font-weight: 700;">0</span>
        </div>
        <div class="live-feed-box" id="job-live-feed">
          <div style="color: var(--text-muted);">รอข้อมูลสด...</div>
        </div>
        <div id="job-error" style="display: none; margin-top: 10px; padding: 10px; border-radius: 8px; background: rgba(248,81,73,0.12); border: 1px solid #f85149; color: #ff7b72; font-size: 12px; white-space: pre-wrap;"></div>
      </div>

    </div>

    <!-- Right Column: Interactive Table Viewer -->
    <div>
      <div class="card">
        <div class="card-title">
          <span id="current-file-title">📄 เลือกไฟล์จากด้านซ้ายเพื่อดูข้อมูล</span>
          <div style="display: flex; gap: 8px; align-items: center;">
            <select id="filter-select" style="width: 140px; margin-bottom: 0;" onchange="loadTableData(1)">
              <option value="all">แสดงทั้งหมด</option>
              <option value="empty">เฉพาะที่ยังไม่แปล</option>
              <option value="translated">เฉพาะที่แปลแล้ว</option>
              <option value="ai">แปลด้วย AI</option>
            </select>
            <input type="text" id="search-input" placeholder="🔍 ค้นหา FormID, ข้อความ, ผู้พูด..." style="width: 200px; margin-bottom: 0;" onkeyup="if(event.key==='Enter') loadTableData(1)">
          </div>
        </div>

        <div class="table-container">
          <table id="main-table">
            <thead>
              <tr id="table-head">
                <th>#</th>
                <th>FormID / ข้อมูล</th>
                <th style="width: 40%;">ภาษาอังกฤษ (EN)</th>
                <th style="width: 40%;">ภาษาไทย (TH) - แก้ไขได้</th>
                <th>เครื่องมือ</th>
              </tr>
            </thead>
            <tbody id="table-body">
              <tr>
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 40px;">กรุณาคลิกเลือกไฟล์ทางซ้ายเพื่อแสดงข้อมูลตาราง</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; font-size: 13px;">
          <span id="pagination-info">0 รายการ</span>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-secondary btn-sm" id="btn-prev" onclick="changePage(-1)">◀ ย้อนหลัง</button>
            <span id="page-num" style="display: flex; align-items: center; padding: 0 8px;">หน้า 1 / 1</span>
            <button class="btn btn-secondary btn-sm" id="btn-next" onclick="changePage(1)">ถัดไป ▶</button>
          </div>
        </div>

      </div>
    </div>

  </div>

  <script>
    let currentFilePath = "";
    let currentPage = 1;
    let totalPages = 1;
    let currentRows = [];
    let pollInterval = null;

    const SETTINGS_KEY = "thaifnv_ai_settings";

    window.onload = function() {
      loadProviderSettings();
      onProviderChange();
      loadFiles();
      checkOllama();
      startStatusPolling();
      bindSettingsAutosave();
    };

    function bindSettingsAutosave() {
      const ids = [
        "provider-select", "deepseek-key", "deepseek-model-select", "deepseek-budget",
        "gemini-key", "gemini-model-select",
        "openai-key", "openai-url", "openai-model",
        "batch-size", "limit-rows", "mode-select"
      ];
      ids.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("change", saveProviderSettings);
        if (el.tagName === "INPUT") el.addEventListener("blur", saveProviderSettings);
      });
      const budgetEl = document.getElementById("deepseek-budget");
      if (budgetEl) budgetEl.addEventListener("change", () => refreshDeepseekBalance());
      const keyEl = document.getElementById("deepseek-key");
      if (keyEl) keyEl.addEventListener("blur", () => {
        if (document.getElementById("provider-select").value === "deepseek") refreshDeepseekBalance();
      });
    }

    function saveProviderSettings(showFeedback) {
      const data = {
        provider: document.getElementById("provider-select").value,
        deepseekKey: document.getElementById("deepseek-key").value,
        deepseekModel: document.getElementById("deepseek-model-select").value,
        deepseekBudget: document.getElementById("deepseek-budget").value,
        geminiKey: document.getElementById("gemini-key").value,
        geminiModel: document.getElementById("gemini-model-select").value,
        openaiKey: document.getElementById("openai-key").value,
        openaiUrl: document.getElementById("openai-url").value,
        openaiModel: document.getElementById("openai-model").value,
        batchSize: document.getElementById("batch-size").value,
        limitRows: document.getElementById("limit-rows").value,
        mode: document.getElementById("mode-select").value,
      };
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(data));
      if (showFeedback) {
        const btn = document.getElementById("btn-save-ai");
        btn.innerText = "✓ จำค่าแล้ว";
        setTimeout(() => { btn.innerText = "💾 จำการตั้งค่า AI"; }, 1500);
      }
    }

    function loadProviderSettings() {
      try {
        const raw = localStorage.getItem(SETTINGS_KEY);
        if (!raw) return;
        const data = JSON.parse(raw);
        if (data.provider) document.getElementById("provider-select").value = data.provider;
        if (data.deepseekKey) document.getElementById("deepseek-key").value = data.deepseekKey;
        if (data.deepseekModel) document.getElementById("deepseek-model-select").value = data.deepseekModel;
        if (data.deepseekBudget) document.getElementById("deepseek-budget").value = data.deepseekBudget;
        if (data.geminiKey) document.getElementById("gemini-key").value = data.geminiKey;
        if (data.geminiModel) document.getElementById("gemini-model-select").value = data.geminiModel;
        if (data.openaiKey) document.getElementById("openai-key").value = data.openaiKey;
        if (data.openaiUrl) document.getElementById("openai-url").value = data.openaiUrl;
        if (data.openaiModel) document.getElementById("openai-model").value = data.openaiModel;
        if (data.batchSize) document.getElementById("batch-size").value = data.batchSize;
        if (data.limitRows != null) document.getElementById("limit-rows").value = data.limitRows;
        if (data.mode) document.getElementById("mode-select").value = data.mode;
      } catch (e) {}
    }

    function formatTokenCount(n) {
      n = Number(n) || 0;
      if (n >= 1000000) return (n / 1000000).toFixed(2) + "M";
      if (n >= 1000) return (n / 1000).toFixed(1) + "k";
      return n.toLocaleString();
    }

    let deepseekBalanceTimer = null;
    function refreshDeepseekBalance() {
      const key = document.getElementById("deepseek-key").value.trim();
      const budget = document.getElementById("deepseek-budget").value;
      const text = document.getElementById("deepseek-token-text");
      const sub = document.getElementById("deepseek-token-sub");
      const fill = document.getElementById("deepseek-token-fill");
      if (!key) {
        text.innerText = "ใส่ API Key แล้วกดเช็คยอด";
        fill.style.width = "0%";
        return;
      }
      text.innerText = "กำลังเช็คยอด...";
      fetch("/api/deepseek_balance", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ api_key: key, budget_usd: budget })
      })
      .then(r => r.json())
      .then(d => {
        if (!d.ok) {
          text.innerText = "เช็คยอดไม่สำเร็จ";
          sub.innerText = d.error || "unknown error";
          fill.style.width = "0%";
          return;
        }
        const used = Number(d.used_usd || 0);
        const total = Number(d.budget_usd || 0);
        const rem = Number(d.remaining_in_budget_usd != null ? d.remaining_in_budget_usd : d.remaining_usd || 0);
        const pct = d.percent_used != null ? Number(d.percent_used) : 0;
        fill.style.width = pct + "%";
        fill.className = "progress-bar-fill " + (pct >= 85 ? "low" : (pct >= 60 ? "warn" : "ok"));
        text.innerText = "$" + used.toFixed(4) + " / $" + total.toFixed(2) + " (" + pct.toFixed(1) + "%)";
        sub.innerText = "เหลือในงบ $" + rem.toFixed(4)
          + " · ยอดในบัญชี " + (d.currency || "USD") + " $" + Number(d.remaining_usd || 0).toFixed(4)
          + (Number(d.remaining_usd || 0) > total ? " (สูงกว่างบที่ตั้ง)" : "");
      })
      .catch(err => {
        text.innerText = "เช็คยอดไม่สำเร็จ";
        sub.innerText = String(err);
        fill.style.width = "0%";
      });
    }

    function getProviderConfig() {
      const provider = document.getElementById("provider-select").value;
      let model = "";
      let apiKey = "";
      let baseUrl = "https://api.openai.com/v1";

      if (provider === "ollama") {
        model = document.getElementById("ollama-model-select").value;
      } else if (provider === "deepseek") {
        apiKey = document.getElementById("deepseek-key").value;
        model = document.getElementById("deepseek-model-select").value;
        baseUrl = "https://api.deepseek.com/v1";
      } else if (provider === "gemini") {
        apiKey = document.getElementById("gemini-key").value;
        model = document.getElementById("gemini-model-select").value;
      } else if (provider === "openai") {
        apiKey = document.getElementById("openai-key").value;
        baseUrl = document.getElementById("openai-url").value;
        model = document.getElementById("openai-model").value;
      }
      return { provider, model, apiKey, baseUrl };
    }

    function checkOllama() {
      fetch('/api/ollama_models')
        .then(r => r.json())
        .then(d => {
          const badge = document.getElementById('ollama-status');
          const sel = document.getElementById('ollama-model-select');
          sel.innerHTML = "";
          if (d.models && d.models.length > 0) {
            badge.innerText = "● Ollama Online (" + d.models.length + " Models)";
            badge.className = "badge badge-green";
            let preferred = "";
            d.models.forEach(m => {
              const opt = document.createElement('option');
              opt.value = m;
              opt.innerText = m;
              sel.appendChild(opt);
              if (m === 'thaifnv-typhoon' || m === 'thaifnv-typhoon:latest') preferred = m;
              else if (!preferred && m.includes('typhoon')) preferred = m;
            });
            if (preferred) sel.value = preferred;
          } else {
            badge.innerText = "Ollama Offline";
            badge.className = "badge";
          }
        })
        .catch(() => {
          document.getElementById('ollama-status').innerText = "Ollama Not Reachable";
        });
    }

    function switchFileTab(tab) {
      document.getElementById('tab-cat-btn').className = tab === 'cat' ? 'tab-btn active' : 'tab-btn';
      document.getElementById('tab-dlc-btn').className = tab === 'dlc' ? 'tab-btn active' : 'tab-btn';
      document.getElementById('file-list-cat').style.display = tab === 'cat' ? 'flex' : 'none';
      document.getElementById('file-list-dlc').style.display = tab === 'dlc' ? 'flex' : 'none';
    }

    function loadFiles() {
      fetch('/api/files')
        .then(r => r.json())
        .then(d => {
          const catContainer = document.getElementById('file-list-cat');
          catContainer.innerHTML = "";
          d.categories.forEach(f => {
            const item = document.createElement('div');
            item.className = 'file-item' + (f.path === currentFilePath ? ' active' : '');
            item.onclick = () => selectFile(f.path, f.name);
            item.innerHTML = `
              <div>
                <strong>${f.name}</strong>
                <div style="color: var(--text-muted); font-size: 11px;">${f.translated.toLocaleString()} / ${f.total.toLocaleString()}</div>
              </div>
              <span class="badge ${f.percent >= 100 ? 'badge-green' : 'badge-amber'}">${f.percent}%</span>
            `;
            catContainer.appendChild(item);
          });

          const dlcContainer = document.getElementById('file-list-dlc');
          dlcContainer.innerHTML = "";
          for (const [dlcName, files] of Object.entries(d.dlcs)) {
            const heading = document.createElement('div');
            heading.style.cssText = "font-weight: 700; color: var(--amber); margin-top: 8px; font-size: 11px; text-transform: uppercase;";
            heading.innerText = dlcName.replace('_', ' ');
            dlcContainer.appendChild(heading);

            files.forEach(f => {
              const item = document.createElement('div');
              item.className = 'file-item' + (f.path === currentFilePath ? ' active' : '');
              item.onclick = () => selectFile(f.path, f.name);
              item.innerHTML = `
                <div>
                  <strong>${f.name}</strong>
                  <div style="color: var(--text-muted); font-size: 11px;">${f.translated.toLocaleString()} / ${f.total.toLocaleString()}</div>
                </div>
                <span class="badge ${f.percent >= 100 ? 'badge-green' : 'badge-amber'}">${f.percent}%</span>
              `;
              dlcContainer.appendChild(item);
            });
          }

          // Select first file by default if none selected
          if (!currentFilePath && d.categories.length > 0) {
            selectFile(d.categories[0].path, d.categories[0].name);
          }
        });
    }

    function selectFile(path, name) {
      currentFilePath = path;
      document.getElementById('current-file-title').innerText = "📄 " + name;
      document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
      currentPage = 1;
      loadTableData(1);
    }

    function loadTableData(page) {
      if (!currentFilePath) return;
      currentPage = page;
      const filter = document.getElementById('filter-select').value;
      const q = document.getElementById('search-input').value;

      fetch(`/api/data?file=${encodeURIComponent(currentFilePath)}&page=${page}&filter=${filter}&q=${encodeURIComponent(q)}`)
        .then(r => r.json())
        .then(d => {
          if (!d.ok) return;
          totalPages = d.pages || 1;
          document.getElementById('page-num').innerText = `หน้า ${d.page} / ${totalPages}`;
          document.getElementById('pagination-info').innerText = `${d.total.toLocaleString()} รายการ`;

          currentRows = d.rows || [];
          const tbody = document.getElementById('table-body');
          tbody.innerHTML = "";

          if (d.rows.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">ไม่พบรายการที่ตรงกับเงื่อนไข</td></tr>`;
            return;
          }

          d.rows.forEach(r => {
            const tr = document.createElement('tr');
            
            let metaHtml = `<strong>${r.FormID || ''}</strong>`;
            if (r.Speaker) {
              metaHtml += `<br><span class="speaker-tag">${escapeHtml(r.Speaker)}</span>`;
            }
            if (r.Emotion) {
              metaHtml += `<div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(r.Emotion)}</div>`;
            }
            if (r.ActorNotes) {
              metaHtml += `<span class="notes-tag">${escapeHtml(r.ActorNotes)}</span>`;
            }

            tr.innerHTML = `
              <td>${r.ID || r._row_idx + 1}</td>
              <td>${metaHtml}</td>
              <td style="white-space: pre-wrap;">${escapeHtml(r.EN || '')}</td>
              <td>
                <textarea class="edit-th" id="th-${r._row_idx}">${escapeHtml(r.TH || '')}</textarea>
              </td>
              <td style="white-space: nowrap;">
                <button class="btn btn-secondary btn-sm" onclick="saveRow(${r._row_idx})">💾 บันทึก</button>
                <button class="btn btn-primary btn-sm" onclick="translateSingleRow(${r._row_idx})">⚡ แปล AI</button>
              </td>
            `;
            tbody.appendChild(tr);
          });
        });
    }

    function saveRow(rowIdx) {
      const thVal = document.getElementById('th-' + rowIdx).value;
      fetch('/api/save_row', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          file: currentFilePath,
          row_idx: rowIdx,
          th: thVal
        })
      })
      .then(r => r.json())
      .then(d => {
        if (d.ok) {
          const btn = event.target;
          btn.innerText = "✓ เซฟแล้ว";
          setTimeout(() => btn.innerText = "💾 บันทึก", 1500);
        } else {
          alert("เกิดข้อผิดพลาดในการเซฟ: " + d.error);
        }
      });
    }

    function translateSingleRow(rowIdx) {
      const r = currentRows.find(x => x._row_idx === rowIdx);
      if (!r) return;
      const enText = r.EN || '';
      const speaker = r.Speaker || '';
      const emotion = r.Emotion || '';

      const btn = event.target;
      btn.innerText = "กำลังแปล...";
      btn.disabled = true;

      const cfg = getProviderConfig();
      if ((cfg.provider === "deepseek" || cfg.provider === "gemini" || cfg.provider === "openai") && !cfg.apiKey) {
        alert("กรุณาใส่ API Key ในช่องตั้งค่า AI ก่อน");
        btn.disabled = false;
        btn.innerText = "⚡ แปล AI";
        return;
      }

      fetch('/api/translate_single', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          en: enText,
          provider: cfg.provider,
          model: cfg.model,
          api_key: cfg.apiKey,
          base_url: cfg.baseUrl,
          speaker: speaker,
          emotion: emotion
        })
      })
      .then(r => r.json())
      .then(d => {
        btn.disabled = false;
        btn.innerText = "⚡ แปล AI";
        if (d.ok) {
          document.getElementById('th-' + rowIdx).value = d.th;
          saveRow(rowIdx);
        } else {
          alert("แปลไม่สำเร็จ: " + d.error);
        }
      })
      .catch(err => {
        btn.disabled = false;
        btn.innerText = "⚡ แปล AI";
        alert("Error: " + err);
      });
    }

    function onProviderChange() {
      const p = document.getElementById('provider-select').value;
      document.getElementById('ollama-fields').style.display = p === 'ollama' ? 'block' : 'none';
      document.getElementById('deepseek-fields').style.display = p === 'deepseek' ? 'block' : 'none';
      document.getElementById('gemini-fields').style.display = p === 'gemini' ? 'block' : 'none';
      document.getElementById('openai-fields').style.display = p === 'openai' ? 'block' : 'none';
      saveProviderSettings();
      if (deepseekBalanceTimer) {
        clearInterval(deepseekBalanceTimer);
        deepseekBalanceTimer = null;
      }
      if (p === 'deepseek') {
        refreshDeepseekBalance();
        deepseekBalanceTimer = setInterval(refreshDeepseekBalance, 30000);
      }
    }

    function startTranslationJob() {
      if (!currentFilePath) {
        alert("กรุณาเลือกไฟล์ก่อนสั่งแปล");
        return;
      }
      const cfg = getProviderConfig();
      if ((cfg.provider === "deepseek" || cfg.provider === "gemini" || cfg.provider === "openai") && !cfg.apiKey) {
        alert("กรุณาใส่ API Key ในช่องตั้งค่า AI ก่อน");
        return;
      }
      saveProviderSettings();

      const mode = document.getElementById('mode-select').value;
      const batchSize = parseInt(document.getElementById('batch-size').value, 10) || 3;
      const limitRaw = document.getElementById('limit-rows').value;
      const limit = limitRaw === '' ? 0 : (parseInt(limitRaw, 10) || 0);

      fetch('/api/job/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          file: currentFilePath,
          provider: cfg.provider,
          model: cfg.model,
          api_key: cfg.apiKey,
          base_url: cfg.baseUrl,
          mode: mode,
          batch_size: batchSize,
          limit: limit
        })
      })
      .then(async r => {
        const text = await r.text();
        let d;
        try { d = JSON.parse(text); }
        catch (e) { throw new Error("เซิร์ฟเวอร์ตอบกลับผิดพลาด (HTTP " + r.status + ")"); }
        if (!d.ok) alert("ไม่สามารถเริ่มงานได้: " + (d.error || "unknown"));
      })
      .catch(err => alert("ไม่สามารถเริ่มงานได้: " + err.message));
    }

    function pauseJob() { fetch('/api/job/pause', {method: 'POST'}); }
    function resumeJob() { fetch('/api/job/resume', {method: 'POST'}); }
    function stopJob() { fetch('/api/job/stop', {method: 'POST'}); }

    function startStatusPolling() {
      setInterval(() => {
        fetch('/api/job/status')
          .then(r => r.json())
          .then(updateJobUI);
      }, 1000);
    }

    let lastJobUiState = "";

    function renderLiveFeed(feed) {
      if (!feed) return;
      document.getElementById('job-live-feed').innerHTML = `
        <div style="font-size: 11px; color: var(--accent); margin-bottom: 2px;">
          [${escapeHtml(feed.source || '')}] ${feed.speaker ? '🗣️ ' + escapeHtml(feed.speaker) : ''}
        </div>
        <div style="color: var(--text-muted);">${escapeHtml(feed.en || '')}</div>
        <div style="color: var(--green); font-weight: 600; margin-top: 4px;">↳ ${escapeHtml(feed.th || '')}</div>
      `;
    }

    function renderJobProgress(st) {
      const pct = st.total_target > 0 ? (st.current_index / st.total_target) * 100 : 0;
      document.getElementById('job-progress-fill').style.width = Math.min(100, pct) + '%';
      document.getElementById('job-counts').innerText = `${(st.current_index || 0).toLocaleString()} / ${(st.total_target || 0).toLocaleString()} (${pct.toFixed(1)}%)`;
      document.getElementById('job-speed').innerText = `${st.speed_per_sec || 0} รายการ/วิ`;
      document.getElementById('job-tokens').innerText =
        formatTokenCount(st.tokens_total || 0) +
        ` (in ${formatTokenCount(st.tokens_in || 0)} / out ${formatTokenCount(st.tokens_out || 0)})`;
      renderLiveFeed(st.live_feed);
    }

    function updateJobUI(st) {
      const card = document.getElementById('job-card');
      const btnStart = document.getElementById('btn-start');
      const btnPause = document.getElementById('btn-pause');
      const btnResume = document.getElementById('btn-resume');
      const btnStop = document.getElementById('btn-stop');
      const errBox = document.getElementById('job-error');
      const stateChanged = st.state !== lastJobUiState;

      if (st.state === 'RUNNING' || st.state === 'PAUSED' || st.state === 'ERROR' || st.state === 'FINISHED' || st.state === 'STOPPED') {
        card.style.display = 'block';
      }

      if (st.state === 'RUNNING' || st.state === 'PAUSED') {
        btnStart.style.display = 'none';
        btnStop.style.display = 'inline-flex';
        btnPause.style.display = st.state === 'RUNNING' ? 'inline-flex' : 'none';
        btnResume.style.display = st.state === 'PAUSED' ? 'inline-flex' : 'none';
        errBox.style.display = 'none';
        let badge = 'RUNNING';
        if (st.state === 'PAUSED') badge = 'PAUSED';
        else if (st.is_stuck) badge = 'ค้าง / รอ API';
        else if (st.live_feed && st.live_feed.source === 'รอ API') badge = 'รอ API...';
        else if (st.live_feed && st.live_feed.source === 'บันทึก') badge = 'กำลังบันทึก...';
        else if (st.live_feed && st.live_feed.source === 'Timeout') badge = 'ข้าม timeout';
        document.getElementById('job-badge').innerText = badge;
        renderJobProgress(st);
        if (st.is_stuck) {
          errBox.style.display = 'block';
          errBox.textContent = "งานดูเหมือนค้าง (ไม่มี progress ~" + (st.stuck_for_sec || 0) + " วินาที). ถ้ายังไม่ขยับ ให้กดหยุดแล้วเริ่มใหม่ — ระบบจะข้าม batch ที่ timeout อัตโนมัติ";
        }
      } else if (st.state === 'FINISHED' || st.state === 'ERROR' || st.state === 'STOPPED') {
        renderJobProgress(st);
        if (st.state === 'FINISHED') {
          document.getElementById('job-badge').innerText = "เสร็จสิ้น";
          document.getElementById('job-progress-fill').style.width = '100%';
          errBox.style.display = 'none';
        } else if (st.state === 'STOPPED') {
          document.getElementById('job-badge').innerText = "หยุดแล้ว";
          errBox.style.display = 'none';
        } else if (st.state === 'ERROR') {
          document.getElementById('job-badge').innerText = "หยุด: เครดิตหมด/API";
          errBox.style.display = 'block';
          errBox.textContent = "งานถูกหยุดอัตโนมัติ — แถวที่แปลแล้วถูกบันทึกไว้แล้ว\\n" + (st.error_msg || "API credit/quota หมด");
        }
        if (stateChanged) {
          loadFiles();
          if (document.getElementById('provider-select').value === 'deepseek') refreshDeepseekBalance();
        }
        btnStart.style.display = 'inline-flex';
        btnPause.style.display = 'none';
        btnResume.style.display = 'none';
        btnStop.style.display = 'none';
      } else {
        // IDLE
        btnStart.style.display = 'inline-flex';
        btnPause.style.display = 'none';
        btnResume.style.display = 'none';
        btnStop.style.display = 'none';
      }
      lastJobUiState = st.state;
    }

    function changePage(delta) {
      const next = currentPage + delta;
      if (next >= 1 && next <= totalPages) {
        loadTableData(next);
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      const div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML;
    }
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    print(f"\n=======================================================")
    print(f"☢️ ThaiFNV Translation Studio Web App")
    print(f"🌐 Server running at: http://127.0.0.1:{PORT}")
    print(f"📂 Workspace: {ROOT_DIR}")
    print(f"=======================================================\n")
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
