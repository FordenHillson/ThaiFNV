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
        GeminiProvider,
        OllamaProvider,
        OpenAICompatibleProvider,
        load_cache,
        save_cache,
    )
except ImportError:
    from fnv_glossary import FNV_TERMS, SYSTEM_PROMPT
    from ai_translator import (
        BaseProvider,
        GeminiProvider,
        OllamaProvider,
        OpenAICompatibleProvider,
        load_cache,
        save_cache,
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
    state: str  # IDLE, RUNNING, PAUSED, FINISHED, ERROR
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
        )

    def get_status(self) -> dict:
        with self.lock:
            d = asdict(self.state)
            if self.state.state in ("RUNNING", "PAUSED") and self.state.start_time > 0:
                elapsed = max(0.1, time.time() - self.state.start_time)
                d["elapsed_sec"] = round(elapsed, 1)
                speed = self.state.translated_count / elapsed
                d["speed_per_sec"] = round(speed, 2)
                rem = max(0, self.state.total_target - self.state.current_index)
                d["eta_sec"] = round(rem / speed, 1) if speed > 0 else 0
            else:
                d["elapsed_sec"] = 0
                d["eta_sec"] = 0
            return d

    def start_job(self, file_path_str: str, provider: BaseProvider, provider_type: str,
                  model_name: str, mode: str = "empty_only", batch_size: int = 5, limit: int = 0) -> dict:
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
                start_time=time.time(),
                speed_per_sec=0.0,
                live_feed=None,
                error_msg="",
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
            self.state.state = "IDLE"
            return {"ok": True}

    def _run_worker(self, file_path: Path, headers: list[str], rows: list[dict],
                    target_indices: list[int], provider: BaseProvider, batch_size: int):
        cache = load_cache()
        save_interval = 20
        total_items = len(target_indices)
        chunk_start = 0
        local_id_counter = 1

        def save_file():
            # Atomic backup and write
            bak_path = file_path.with_suffix(".csv.bak")
            shutil.copy2(file_path, bak_path)
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
            save_cache(cache)

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
                        self.state.live_feed = {
                            "en": en,
                            "th": th_term,
                            "speaker": r.get("Speaker", ""),
                            "source": "Glossary",
                        }
                    continue

                # 3. Queue for AI
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

                batch_items.append(payload)
                batch_map[local_id_counter] = row_idx
                local_id_counter += 1

            if batch_items:
                try:
                    translations = provider.translate_batch(batch_items)
                    for bid, th in translations.items():
                        if bid in batch_map:
                            t_idx = batch_map[bid]
                            target_row = rows[t_idx]
                            target_row["TH"] = th
                            target_row["Status"] = "ai"
                            cache[target_row["EN"].strip()] = th
                            with self.lock:
                                self.state.translated_count += 1
                                self.state.current_index += 1
                                self.state.live_feed = {
                                    "en": target_row["EN"],
                                    "th": th,
                                    "speaker": target_row.get("Speaker", ""),
                                    "source": "AI",
                                }
                except Exception as e:
                    with self.lock:
                        self.state.error_msg = str(e)
                    time.sleep(1)

            if self.state.current_index % save_interval == 0:
                save_file()

        save_file()
        with self.lock:
            self.state.state = "FINISHED" if not self.stop_event.is_set() else "IDLE"


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
        return ["scb10x/typhoon2.1-gemma3-12b:latest", "qwen3.5:9b"]


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

    if provider_type == "ollama":
        provider = OllamaProvider(model=model_name or "scb10x/typhoon2.1-gemma3-12b:latest")
    elif provider_type == "gemini":
        provider = GeminiProvider(api_key=api_key, model=model_name or "gemini-2.5-flash")
    elif provider_type == "openai":
        provider = OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=model_name or "gpt-4o-mini")
    else:
        return jsonify({"ok": False, "error": "Unsupported provider"}), 400

    try:
        payload = [{"id": 1, "en": en_text}]
        if speaker:
            payload[0]["speaker"] = speaker
        if emotion:
            payload[0]["emotion"] = emotion

        res = provider.translate_batch(payload)
        th_res = res.get(1, "").strip()
        return jsonify({"ok": True, "th": th_res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/job/start", methods=["POST"])
def api_job_start():
    body = request.get_json() or {}
    file_path = body.get("file", "")
    provider_type = body.get("provider", "ollama")
    model_name = body.get("model", "")
    api_key = body.get("api_key", "")
    base_url = body.get("base_url", "https://api.openai.com/v1")
    mode = body.get("mode", "empty_only")
    batch_size = int(body.get("batch_size", 5))
    limit = int(body.get("limit", 0))

    if provider_type == "ollama":
        provider = OllamaProvider(model=model_name or "scb10x/typhoon2.1-gemma3-12b:latest")
    elif provider_type == "gemini":
        if not api_key:
            return jsonify({"ok": False, "error": "Gemini API Key is required"}), 400
        provider = GeminiProvider(api_key=api_key, model=model_name or "gemini-2.5-flash")
    elif provider_type == "openai":
        if not api_key:
            return jsonify({"ok": False, "error": "API Key is required"}), 400
        provider = OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=model_name or "gpt-4o-mini")
    else:
        return jsonify({"ok": False, "error": "Unknown provider"}), 400

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
    .live-feed-box { background: #090d13; border: 1px solid var(--border); border-radius: 6px; padding: 10px; font-size: 12px; min-height: 70px; }

    /* Data Table */
    .table-container { overflow-x: auto; max-height: 600px; border: 1px solid var(--border); border-radius: 8px; }
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
          <option value="gemini">Google Gemini API</option>
          <option value="openai">OpenAI / OpenRouter / DeepSeek</option>
        </select>

        <div id="ollama-fields">
          <label>โมเดลในเครื่อง (Ollama Models):</label>
          <select id="ollama-model-select"></select>
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
          <input type="text" id="openai-url" value="https://api.openai.com/v1" placeholder="https://api.deepseek.com/v1">
          <label>Model Name:</label>
          <input type="text" id="openai-model" value="gpt-4o-mini" placeholder="deepseek-chat">
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
          <div>
            <label>Batch Size:</label>
            <input type="number" id="batch-size" value="5" min="1" max="25">
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
        <div class="live-feed-box" id="job-live-feed">
          <div style="color: var(--text-muted);">รอข้อมูลสด...</div>
        </div>
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

    window.onload = function() {
      loadFiles();
      checkOllama();
      startStatusPolling();
    };

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
            d.models.forEach(m => {
              const opt = document.createElement('option');
              opt.value = m;
              opt.innerText = m;
              if (m.includes('typhoon')) opt.selected = true;
              sel.appendChild(opt);
            });
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

      const provider = document.getElementById('provider-select').value;
      let model = "";
      let apiKey = "";
      let baseUrl = "https://api.openai.com/v1";

      if (provider === 'ollama') model = document.getElementById('ollama-model-select').value;
      else if (provider === 'gemini') {
        apiKey = document.getElementById('gemini-key').value;
        model = document.getElementById('gemini-model-select').value;
      } else if (provider === 'openai') {
        apiKey = document.getElementById('openai-key').value;
        baseUrl = document.getElementById('openai-url').value;
        model = document.getElementById('openai-model').value;
      }

      fetch('/api/translate_single', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          en: enText,
          provider: provider,
          model: model,
          api_key: apiKey,
          base_url: baseUrl,
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
      document.getElementById('gemini-fields').style.display = p === 'gemini' ? 'block' : 'none';
      document.getElementById('openai-fields').style.display = p === 'openai' ? 'block' : 'none';
    }

    function startTranslationJob() {
      if (!currentFilePath) {
        alert("กรุณาเลือกไฟล์ก่อนสั่งแปล");
        return;
      }
      const provider = document.getElementById('provider-select').value;
      let model = "";
      let apiKey = "";
      let baseUrl = "https://api.openai.com/v1";

      if (provider === 'ollama') model = document.getElementById('ollama-model-select').value;
      else if (provider === 'gemini') {
        apiKey = document.getElementById('gemini-key').value;
        model = document.getElementById('gemini-model-select').value;
      } else if (provider === 'openai') {
        apiKey = document.getElementById('openai-key').value;
        baseUrl = document.getElementById('openai-url').value;
        model = document.getElementById('openai-model').value;
      }

      const mode = document.getElementById('mode-select').value;
      const batchSize = document.getElementById('batch-size').value;
      const limit = document.getElementById('limit-rows').value;

      fetch('/api/job/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          file: currentFilePath,
          provider: provider,
          model: model,
          api_key: apiKey,
          base_url: baseUrl,
          mode: mode,
          batch_size: batchSize,
          limit: limit
        })
      })
      .then(r => r.json())
      .then(d => {
        if (!d.ok) {
          alert("ไม่สามารถเริ่มงานได้: " + d.error);
        }
      });
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

    function updateJobUI(st) {
      const card = document.getElementById('job-card');
      const btnStart = document.getElementById('btn-start');
      const btnPause = document.getElementById('btn-pause');
      const btnResume = document.getElementById('btn-resume');
      const btnStop = document.getElementById('btn-stop');

      if (st.state === 'RUNNING' || st.state === 'PAUSED') {
        card.style.display = 'block';
        btnStart.style.display = 'none';
        btnStop.style.display = 'inline-flex';
        btnPause.style.display = st.state === 'RUNNING' ? 'inline-flex' : 'none';
        btnResume.style.display = st.state === 'PAUSED' ? 'inline-flex' : 'none';

        const pct = st.total_target > 0 ? (st.current_index / st.total_target) * 100 : 0;
        document.getElementById('job-progress-fill').style.width = pct + '%';
        document.getElementById('job-badge').innerText = st.state;
        document.getElementById('job-counts').innerText = `${st.current_index.toLocaleString()} / ${st.total_target.toLocaleString()} (${pct.toFixed(1)}%)`;
        document.getElementById('job-speed').innerText = `${st.speed_per_sec} รายการ/วิ`;

        if (st.live_feed) {
          document.getElementById('job-live-feed').innerHTML = `
            <div style="font-size: 11px; color: var(--accent); margin-bottom: 2px;">
              [${st.live_feed.source}] ${st.live_feed.speaker ? '🗣️ ' + escapeHtml(st.live_feed.speaker) : ''}
            </div>
            <div style="color: var(--text-muted);">${escapeHtml(st.live_feed.en)}</div>
            <div style="color: var(--green); font-weight: 600; margin-top: 4px;">↳ ${escapeHtml(st.live_feed.th)}</div>
          `;
        }
      } else {
        if (st.state === 'FINISHED') {
          document.getElementById('job-badge').innerText = "เสร็จสิ้น";
          document.getElementById('job-progress-fill').style.width = '100%';
          loadFiles(); // refresh counts
        }
        btnStart.style.display = 'inline-flex';
        btnPause.style.display = 'none';
        btnResume.style.display = 'none';
        btnStop.style.display = 'none';
      }
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
