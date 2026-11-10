#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate Modelfile.thaifnv-typhoon from fnv_glossary.SYSTEM_PROMPT and optionally ollama create."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.fnv_glossary import SYSTEM_PROMPT  # noqa: E402

MODELFILE = Path(__file__).resolve().parent / "Modelfile.thaifnv-typhoon"
MODEL_NAME = "thaifnv-typhoon"
BASE = "scb10x/typhoon2.1-gemma3-12b:latest"


def write_modelfile() -> Path:
    prompt = SYSTEM_PROMPT.strip().replace('"""', "'''")
    body = (
        f"FROM {BASE}\n\n"
        "PARAMETER temperature 0.15\n"
        "PARAMETER top_p 0.9\n"
        "PARAMETER num_ctx 8192\n\n"
        'SYSTEM """\n'
        f"{prompt}\n"
        '"""\n'
    )
    MODELFILE.write_text(body, encoding="utf-8")
    return MODELFILE


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ThaiFNV Ollama model")
    parser.add_argument("--create", action="store_true", help="Run ollama create after writing Modelfile")
    parser.add_argument("--name", default=MODEL_NAME, help="Ollama model name")
    args = parser.parse_args()

    path = write_modelfile()
    print(f"Wrote {path} ({path.stat().st_size} bytes)")

    if args.create:
        cmd = ["ollama", "create", args.name, "-f", str(path)]
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
