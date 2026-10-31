from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

import pytest

from names_compact_pack import (  # noqa: E402
    build_en_to_th,
    build_unique_index,
    classify_en,
    load_proper_nouns,
    merge_into_rows,
    validate_out_pack,
    write_packs,
    _require_force_if_out_has_packs,
)


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


def test_build_aborts_when_out_has_packs_without_force(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "u_0001.tsv").write_text("1\tแปลแล้ว\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _require_force_if_out_has_packs(out_dir, force=False)
    assert exc.value.code == 1


def test_build_allowed_when_out_has_packs_with_force(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "u_0001.tsv").write_text("1\tแปลแล้ว\n", encoding="utf-8")
    _require_force_if_out_has_packs(out_dir, force=True)


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
