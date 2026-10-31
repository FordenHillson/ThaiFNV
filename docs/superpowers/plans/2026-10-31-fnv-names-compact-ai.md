# FNV_Names Compact AI Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เติมคอลัมน์ `TH` ใน `extracted/sheets/FNV_Names.csv` ให้ครบด้วย Cursor agent ผ่าน Compact Unique Pack + กรองอัตโนมัติ แล้วได้ CSV พร้อมอัปโหลด Google Sheet

**Architecture:** สคริปต์ `names_compact_pack.py` สร้าง EN ไม่ซ้ำ → กรอง `keep`/`need_ai` → แพ็ก TSV สั้น → agent แปลทีละแพ็กในแชท → merge กลับ CSV เดิมแบบ resume ได้ ไม่แตะ MT engine เดิมและไม่ push Sheets/ESP

**Tech Stack:** Python 3.11+ stdlib (`csv`, `json`, `argparse`, `pathlib`, `re`, `tempfile`), pytest, Cursor agent ในแชท

## Global Constraints

- ผู้แปลหลัก: Cursor agent ในแชทเท่านั้น (ไม่ใช้ `mt_seed_local` / Google / MyMemory เป็น engine หลัก)
- คุณภาพสูง: โทน Fallout, UI สั้นชัด
- ชื่อคน / องค์กร / สถานที่หลัก / ย่อหน้า → คง EN
- ไม่ดึง TM จาก `FNV_Messages`
- เป้าหมายไฟล์เดียว: `extracted/sheets/FNV_Names.csv`
- สถานะที่ใช้: `ai` หรือ `keep` เท่านั้น (ห้ามตั้ง `mt`)
- แพ็ก: `n\tEN` / `n\tTH` · 80–100 บรรทัด · ไม่ใส่ FormID/EditorID/ประเภท
- นอกขอบเขต: Sheets API, ESP import, ชีตอื่น
- Commit: ทำเฉพาะเมื่อผู้ใช้สั่ง commit ในรอบนั้น

---

## File structure

| Path | Responsibility |
|---|---|
| `corpus/names_glossary_short.md` | กฎสั้น + allowlist คง EN + คำแปลที่ล็อก |
| `pipeline/names_compact_pack.py` | build / merge / status / validate pack |
| `pipeline/tests/test_names_compact_pack.py` | unit tests |
| `extracted/sheets/names_packs/en_index.json` | map `n→EN`, keep list, pack meta |
| `extracted/sheets/names_packs/in/u_XXXX.tsv` | แพ็กรอแปล |
| `extracted/sheets/names_packs/out/u_XXXX.tsv` | ผลแปล |
| `extracted/sheets/FNV_Names.csv` | เป้าหมาย merge |

Spec อ้างอิง: `docs/superpowers/specs/2026-10-31-fnv-names-compact-ai-design.md`

---

### Task 1: Glossary สั้น

**Files:**
- Create: `corpus/names_glossary_short.md`

**Interfaces:**
- Consumes: นโยบายจาก spec (คง EN ชื่อเฉพาะ, แปลคำทั่วไป)
- Produces: เอกสารที่ agent และสคริปต์ (allowlist) อ่านได้

- [ ] **Step 1: สร้างไฟล์ glossary**

สร้าง `corpus/names_glossary_short.md` ด้วยเนื้อหาประมาณนี้ (ปรับคำล็อกได้เล็กน้อยตอน implement แต่ต้องครบหมวด):

```markdown
# FNV Names — glossary สั้น

## กฎ
- แปลเฉพาะคำทั่วไป; คง EN สำหรับชื่อคน / องค์กร / สถานที่หลัก / ย่อหน้า
- ทั้งสตริงเป็นชื่อเฉพาะล้วน → คง EN ทั้งสตริง
- สั้น กระชับ UI; ไม่ใส่คำอธิบายในวงเล็บ
- ห้ามดึงคำแปลจาก FNV_Messages

## คง EN (allowlist / ตัวอย่าง)
NCR, Caesar, Caesar's Legion, Legion, Brotherhood of Steel, Enclave,
Goodsprings, Primm, Novac, New Vegas, The Strip, Freeside, Westside,
Mr. House, Yes Man, Vault 21, Vault 22, Vault 3, Vault 11, Vault 19, Vault 34,
Boone, Cass, Veronica, Arcade, Lily, Raul, ED-E, Rex, Benny, Swank,
Powder Gangers, Great Khans, Boomers, Omertas, White Glove Society,
Followers of the Apocalypse, Gun Runners, Crimson Caravan

## คำทั่วไปที่ล็อก
| EN | TH |
|---|---|
| Trooper | ทหาร |
| Ranger | เรนเจอร์ |
| Door | ประตู |
| Locker | ตู้ล็อกเกอร์ |
| Desk | โต๊ะ |
| Metal Box | กล่องโลหะ |
| Ammunition Box | กล่องกระสุน |
| Settler | ผู้อพยพ |
| Merchant | พ่อค้า |
| Guard | ยาม |
| Doctor | หมอ |
| Key | กุญแจ |
| Note | บันทึก |
| Terminal | เทอร์มินัล |
```

- [ ] **Step 2: ตรวจว่าไฟล์อ่านได้**

Run:

```powershell
Get-Content -Path "corpus\names_glossary_short.md" -TotalCount 20 -Encoding UTF8
```

Expected: เห็นหัวข้อ `# FNV Names` และหมวด `## กฎ`

---

### Task 2: ฟังก์ชันจัดประเภท EN + เทส

**Files:**
- Create: `pipeline/names_compact_pack.py`
- Create: `pipeline/tests/test_names_compact_pack.py`
- Create: `pipeline/tests/conftest.py` (ว่างหรือเพิ่ม `sys.path` ถ้าจำเป็น)

**Interfaces:**
- Consumes: รายการ proper-noun จาก glossary (โหลดเป็น `frozenset[str]` แบบ case-sensitive ตามข้อความในเกม)
- Produces:
  - `load_proper_nouns(glossary_path: Path) -> frozenset[str]`
  - `classify_en(en: str, proper: frozenset[str]) -> tuple[str, str]`  
    คืน `(bucket, note)` โดย `bucket ∈ {"keep", "need_ai"}` และ `note` เป็น `proper-noun` / `editorid-like` / `""`

- [ ] **Step 1: เขียนเทสที่ล้มก่อน**

`pipeline/tests/test_names_compact_pack.py`:

```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from names_compact_pack import classify_en, load_proper_nouns  # noqa: E402


def test_keep_exact_proper_noun():
    proper = frozenset({"NCR", "Goodsprings", "Mr. House"})
    assert classify_en("Goodsprings", proper) == ("keep", "proper-noun")
    assert classify_en("Mr. House", proper) == ("keep", "proper-noun")


def test_need_ai_for_general_phrase():
    proper = frozenset({"NCR"})
    assert classify_en("Metal Box", proper) == ("need_ai", "")
    assert classify_en("NCR Trooper", proper) == ("need_ai", "")


def test_editorid_like_keep():
    proper = frozenset()
    assert classify_en("NCRTrooperVendor", proper) == ("keep", "editorid-like")
    assert classify_en("GasValve", proper) == ("keep", "editorid-like")


def test_load_proper_nouns_from_glossary(tmp_path: Path):
    p = tmp_path / "g.md"
    p.write_text(
        "## คง EN\nNCR, Goodsprings, Mr. House\n\n## อื่น\nTrooper | ทหาร\n",
        encoding="utf-8",
    )
    nouns = load_proper_nouns(p)
    assert "NCR" in nouns
    assert "Goodsprings" in nouns
    assert "Mr. House" in nouns
```

- [ ] **Step 2: รันเทสให้ล้ม**

Run:

```powershell
cd D:\backup\github\ThaiFNV
python -m pytest pipeline/tests/test_names_compact_pack.py -v
```

Expected: FAIL (module / functions ยังไม่มี) หรือ import error

- [ ] **Step 3: implement ขั้นต่ำใน `pipeline/names_compact_pack.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""names_compact_pack.py — Compact Unique Pack สำหรับแปล FNV_Names ด้วย Cursor agent"""
from __future__ import annotations

import re
from pathlib import Path

EDITORID_LIKE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])[A-Za-z0-9_]+$")


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
```

- [ ] **Step 4: รันเทสให้ผ่าน**

Run:

```powershell
python -m pytest pipeline/tests/test_names_compact_pack.py -v
```

Expected: PASS ทั้ง 4 เคส

---

### Task 3: Unique index + สร้างแพ็ก `in/`

**Files:**
- Modify: `pipeline/names_compact_pack.py`
- Modify: `pipeline/tests/test_names_compact_pack.py`

**Interfaces:**
- Consumes: `classify_en`, `load_proper_nouns`
- Produces:
  - `FIELDS = ["ID","ประเภท","FormID","EditorID","EN","TH","สถานะ","หมายเหตุ"]`
  - `build_unique_index(rows, proper) -> dict` รูปแบบ:
    ```python
    {
      "version": 1,
      "source": "FNV_Names.csv",
      "entries": [{"n": 1, "en": "...", "bucket": "need_ai"|"keep", "note": "..."}],
      "packs": [{"id": "u_0001", "n_from": 1, "n_to": 100, "count": 100}]
    }
    ```
  - `write_packs(index, in_dir: Path, pack_size: int = 100) -> list[str]`  
    เขียนเฉพาะ `need_ai` เป็น `n\tEN\n` เรียง `n` · แพ็กละ ≤ `pack_size` (ค่าเริ่มต้น 100; อนุญาต 80–100 ตาม spec)

- [ ] **Step 1: เพิ่มเทส build**

```python
from names_compact_pack import build_unique_index, write_packs


def test_build_unique_and_packs(tmp_path: Path):
    rows = [
        {"EN": "Metal Box"},
        {"EN": "Metal Box"},
        {"EN": "Goodsprings"},
        {"EN": "NCRTrooperVendor"},
        {"EN": "Gas Valve"},
    ]
    proper = frozenset({"Goodsprings"})
    index = build_unique_index(rows, proper)
    ens = {e["en"]: e for e in index["entries"]}
    assert ens["Metal Box"]["bucket"] == "need_ai"
    assert ens["Goodsprings"]["bucket"] == "keep"
    assert ens["NCRTrooperVendor"]["bucket"] == "keep"
    need = [e for e in index["entries"] if e["bucket"] == "need_ai"]
    assert len(need) == 2  # Metal Box, Gas Valve
    in_dir = tmp_path / "in"
    pack_ids = write_packs(index, in_dir, pack_size=1)
    assert pack_ids == ["u_0001", "u_0002"]
    assert (in_dir / "u_0001.tsv").read_text(encoding="utf-8").count("\n") >= 1
```

- [ ] **Step 2: รันเทสให้ล้ม**

Run: `python -m pytest pipeline/tests/test_names_compact_pack.py::test_build_unique_and_packs -v`  
Expected: FAIL (functions missing)

- [ ] **Step 3: implement `build_unique_index` + `write_packs`**

กติกา:

- เก็บลำดับ EN แรกที่เจอ
- ใส่ `n` รันต่อเนื่องเฉพาะแถว `need_ai` (เริ่มที่ 1) สำหรับแพ็ก; รายการ `keep` อยู่ใน index แต่ไม่มี `n` สำหรับแพ็ก หรือใช้ `n=null`
- แนะนำ: `need_ai` ได้ `n` 1..N; `keep` ได้ `"n": null`
- `write_packs` อัปเดต `index["packs"]` และคืน list id

ตัวอย่างโครง:

```python
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
        pid = f"u_{len(pack_ids)+1:04d}"
        path = in_dir / f"{pid}.tsv"
        lines = [f"{e['n']}\t{e['en']}" for e in chunk]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        packs.append({
            "id": pid,
            "n_from": chunk[0]["n"],
            "n_to": chunk[-1]["n"],
            "count": len(chunk),
        })
        pack_ids.append(pid)
    index["packs"] = packs
    return pack_ids
```

- [ ] **Step 4: รันเทสให้ผ่าน**

Run: `python -m pytest pipeline/tests/test_names_compact_pack.py -v`  
Expected: PASS ทั้งหมด

---

### Task 4: Validate out-pack + merge เข้า CSV

**Files:**
- Modify: `pipeline/names_compact_pack.py`
- Modify: `pipeline/tests/test_names_compact_pack.py`

**Interfaces:**
- Consumes: index + `out/*.tsv`
- Produces:
  - `validate_out_pack(in_path: Path, out_path: Path) -> list[str]`  
    คืน list ข้อผิดพลาด (ว่าง = ผ่าน): จำนวนบรรทัดเท่ากัน, `n` ครบไม่ซ้ำ, TH ไม่ว่าง, แท็บพอดี 1 ตัวคั่น
  - `build_en_to_th(index: dict, out_dir: Path) -> dict[str, tuple[str, str, str]]`  
    คืน `EN -> (TH, สถานะ, หมายเหตุ)` จาก keep + out ที่ validate ผ่าน
  - `merge_into_rows(rows: list[dict], en_map: dict[str, tuple[str, str, str]]) -> tuple[int, int]`  
    คืน `(filled, skipped)` · ไม่ทับถ้า `TH` ไม่ว่าง หรือ `สถานะ in {"ok","fix"}`
  - `atomic_write_csv(path: Path, rows: list[dict]) -> None` ใช้ `FIELDS` + utf-8-sig

- [ ] **Step 1: เขียนเทส validate/merge**

```python
from names_compact_pack import (
    validate_out_pack,
    build_en_to_th,
    merge_into_rows,
    atomic_write_csv,
    FIELDS,
)


def test_validate_out_pack_ok(tmp_path: Path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.tsv"
    inp.write_text("1\tMetal Box\n2\tGas Valve\n", encoding="utf-8")
    out.write_text("1\tกล่องโลหะ\n2\tวาล์วแก๊ส\n", encoding="utf-8")
    assert validate_out_pack(inp, out) == []


def test_validate_out_pack_missing_th(tmp_path: Path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.tsv"
    inp.write_text("1\tMetal Box\n", encoding="utf-8")
    out.write_text("1\t\n", encoding="utf-8")
    errs = validate_out_pack(inp, out)
    assert errs


def test_merge_keep_and_ai(tmp_path: Path):
    index = {
        "entries": [
            {"n": None, "en": "Goodsprings", "bucket": "keep", "note": "proper-noun"},
            {"n": 1, "en": "Metal Box", "bucket": "need_ai", "note": ""},
        ],
        "packs": [{"id": "u_0001", "n_from": 1, "n_to": 1, "count": 1}],
    }
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "u_0001.tsv").write_text("1\tกล่องโลหะ\n", encoding="utf-8")
    # in path for validate: build_en_to_th should validate using matching in/ if provided
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "u_0001.tsv").write_text("1\tMetal Box\n", encoding="utf-8")
    en_map = build_en_to_th(index, out_dir, in_dir)
    assert en_map["Goodsprings"] == ("Goodsprings", "keep", "proper-noun")
    assert en_map["Metal Box"][0] == "กล่องโลหะ"
    assert en_map["Metal Box"][1] == "ai"
    rows = [
        {"ID": "1", "ประเภท": "X", "FormID": "0", "EditorID": "a", "EN": "Metal Box", "TH": "", "สถานะ": "", "หมายเหตุ": ""},
        {"ID": "2", "ประเภท": "X", "FormID": "0", "EditorID": "b", "EN": "Goodsprings", "TH": "", "สถานะ": "", "หมายเหตุ": ""},
        {"ID": "3", "ประเภท": "X", "FormID": "0", "EditorID": "c", "EN": "Metal Box", "TH": "อย่าทับ", "สถานะ": "ok", "หมายเหตุ": ""},
    ]
    filled, skipped = merge_into_rows(rows, en_map)
    assert rows[0]["TH"] == "กล่องโลหะ" and rows[0]["สถานะ"] == "ai"
    assert rows[1]["TH"] == "Goodsprings" and rows[1]["สถานะ"] == "keep"
    assert rows[2]["TH"] == "อย่าทับ"
    assert filled == 2 and skipped == 1
```

หมายเหตุ implement: `build_en_to_th(index, out_dir, in_dir: Path | None = None)` — ถ้ามี `in_dir` ให้ validate คู่ไฟล์ก่อน; แพ็กที่พังให้ raise `ValueError` พร้อมรวม errors

- [ ] **Step 2: รันเทสให้ล้ม → implement → รันให้ผ่าน**

Run: `python -m pytest pipeline/tests/test_names_compact_pack.py -v`  
Expected ท้ายสุด: PASS

รายละเอียด `validate_out_pack`:

```python
def validate_out_pack(in_path: Path, out_path: Path) -> list[str]:
    errs: list[str] = []
    if not out_path.exists():
        return [f"missing out: {out_path.name}"]
    in_lines = [ln for ln in in_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out_lines = [ln for ln in out_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(in_lines) != len(out_lines):
        errs.append(f"line count {len(out_lines)} != {len(in_lines)}")
    in_ns = []
    out_map = {}
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
```

`atomic_write_csv`: เขียน temp ในโฟลเดอร์เดียวกันแล้ว `replace`

---

### Task 5: CLI `build` / `merge` / `status` / `next`

**Files:**
- Modify: `pipeline/names_compact_pack.py`

**Interfaces:**
- Consumes: ฟังก์ชัน Task 2–4
- Produces: CLI entrypoint

Paths คงที่:

```python
ROOT = Path(__file__).resolve().parents[1]
SHEETS = ROOT / "extracted" / "sheets"
CSV_PATH = SHEETS / "FNV_Names.csv"
PACK_ROOT = SHEETS / "names_packs"
IN_DIR = PACK_ROOT / "in"
OUT_DIR = PACK_ROOT / "out"
INDEX_PATH = PACK_ROOT / "en_index.json"
GLOSSARY = ROOT / "corpus" / "names_glossary_short.md"
```

- [ ] **Step 1: เพิ่ม `main()`**

คำสั่ง:

```text
python pipeline/names_compact_pack.py build [--pack-size 100]
python pipeline/names_compact_pack.py merge
python pipeline/names_compact_pack.py status
python pipeline/names_compact_pack.py next
```

พฤติกรรม:

- `build`: อ่าน CSV + glossary → index → ล้าง/สร้าง `in/` ใหม่ → เขียน `en_index.json` → พิมพ์จำนวน unique / keep / need_ai / packs
- `merge`: โหลด index + validate ทุกแพ็กที่มีใน `index["packs"]` ที่ `out/` มีไฟล์ → รวม keep เสมอ → merge CSV → atomic write → พิมพ์ filled/skipped; ถ้าแพ็กยังไม่มี out ให้ข้ามแพ็กนั้น (partial merge ได้) แต่ยัง apply keep + out ที่มี
- `status`: จำนวนแถวที่ TH ว่าง, จำนวนแพ็กที่ out ครบ/ขาด
- `next`: พิมพ์ path ของแพ็ก `in/` แรกที่ยังไม่มี `out/` คู่กัน (สำหรับ agent)

- [ ] **Step 2: smoke build บน CSV จริง**

Run:

```powershell
python pipeline/names_compact_pack.py build --pack-size 100
python pipeline/names_compact_pack.py status
python pipeline/names_compact_pack.py next
```

Expected:

- สร้าง `extracted/sheets/names_packs/en_index.json`
- มีไฟล์ `in/u_0001.tsv` ขึ้นไป
- `status` แสดง TH ว่าง ~13177 และ packs pending > 0
- `next` ชี้ `...\in\u_0001.tsv`

- [ ] **Step 3: ตรวจแพ็กแรกไม่มี FormID**

Run:

```powershell
Get-Content extracted\sheets\names_packs\in\u_0001.tsv -TotalCount 5 -Encoding UTF8
```

Expected: บรรทัดแบบ `1\tSome English Name` เท่านั้น

---

### Task 6: แปลแพ็กด้วย Cursor agent (วนจนครบ)

**Files:**
- Create: `extracted/sheets/names_packs/out/u_XXXX.tsv` (หลายไฟล์)
- Modify: `extracted/sheets/FNV_Names.csv` (ผ่าน `merge` เป็นระยะ)

**Interfaces:**
- Consumes: `corpus/names_glossary_short.md`, `in/u_XXXX.tsv`, คำสั่ง `next` / `merge` / `status`
- Produces: `out/u_XXXX.tsv` ครบทุกแพ็ก

- [ ] **Step 1: อ่าน glossary ครั้งเดียวต่อเซสชัน**

อ่าน `corpus/names_glossary_short.md` แล้วจำกฎ

- [ ] **Step 2: ลูปแปล**

ทำซ้ำจน `python pipeline/names_compact_pack.py next` รายงานว่าไม่มีแพ็กค้าง:

1. รัน `next` ได้ path แพ็ก
2. อ่านไฟล์ `in` ทั้งไฟล์
3. เขียน `out/<same_id>.tsv` เป็น `n\tTH` จำนวนเท่ากัน
4. ยึด glossary: คง EN ชื่อเฉพาะ; แปลคำทั่วไป; สั้น
5. ทุก ๆ 5 แพ็ก: รัน `merge` แล้ว `status`

ตัวอย่างคำสั่งช่วย:

```powershell
python pipeline/names_compact_pack.py next
# ... เขียน out ...
python pipeline/names_compact_pack.py merge
python pipeline/names_compact_pack.py status
```

- [ ] **Step 3: QA สุ่มต่อแพ็กเมื่อสงสัย**

ถ้าชื่อกำกวม ให้ตรวจ 5–10 บรรทัดในแชทก่อนปิดแพ็ก — ไม่ต้อง QA ทุกบรรทัด

- [ ] **Step 4: merge สุดท้าย**

Run:

```powershell
python pipeline/names_compact_pack.py merge
python pipeline/names_compact_pack.py status
```

Expected: แพ็กค้าง = 0 · แถวที่ TH ว่าง = 0 (หรือเหลือน้อยมากเฉพาะเคสที่ตั้งใจ — ตาม success criteria ต้องเป็น 0)

---

### Task 7: Verification ส่งมอบ CSV

**Files:**
- Verify: `extracted/sheets/FNV_Names.csv`

- [ ] **Step 1: นับความครบ**

```powershell
python -c "import csv; p=r'extracted/sheets/FNV_Names.csv'; rows=list(csv.DictReader(open(p,encoding='utf-8-sig',newline=''))); empty=sum(1 for r in rows if not (r.get('TH') or '').strip()); st={};
for r in rows:
 s=(r.get('สถานะ') or '').strip() or '(empty)'; st[s]=st.get(s,0)+1
print('rows',len(rows),'empty_TH',empty,'status',st)"
```

Expected: `empty_TH 0` · สถานะมีแค่ `ai` / `keep` (ไม่มี `mt`)

- [ ] **Step 2: สุ่มตรวจนโยบายชื่อเฉพาะ**

ตรวจอย่างน้อย: `Goodsprings`, `NCR` (ถ้ามีสตริงล้วน), `Mr. House` → `TH` เท่า `EN` และ `สถานะ=keep`

- [ ] **Step 3: ยืนยันจำนวนแถวไม่เปลี่ยน**

Expected: 13177 แถวข้อมูล (+ header) ตามของเดิม

- [ ] **Step 4: บอกผู้ใช้ว่า CSV พร้อมอัปโหลด Google Sheet**

ไม่รัน Sheets sync / ESP ในงานนี้

---

## Plan self-review

| Spec requirement | Task |
|---|---|
| Glossary สั้น | Task 1 |
| กรอง keep / need_ai / editorid-like | Task 2 |
| Unique pack TSV 80–100 | Task 3, 5 (`--pack-size`) |
| Agent contract n\\tTH | Task 6 |
| Merge ไม่ทับ ok/fix / มี TH | Task 4 |
| atomic CSV + resume | Task 4–6 |
| status / next | Task 5 |
| CSV-only ส่ง Sheet ด้วยมือ | Task 7 + Out of scope |
| ไม่ใช้ mt_seed | Global Constraints + Task 6 |

Placeholder scan: ไม่มี TBD/TODO ที่ค้าง  
Type consistency: `classify_en` → `build_unique_index` → `write_packs` → `build_en_to_th` → `merge_into_rows` ใช้ `bucket`/`note`/`n` ชุดเดียวกัน
