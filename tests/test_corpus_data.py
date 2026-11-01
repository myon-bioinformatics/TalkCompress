"""#135 で追加した口語・文字化け・混在文コーパスの中身の検査（形式・数値の整合は corpus_manifest.check）。"""
from __future__ import annotations

import json
import pathlib

import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

CORPUS = pathlib.Path(__file__).parent / "fixtures" / "corpus"
ENTRIES = [e for e in json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))["entries"]
           if e.get("generator") == "scripts/build_corpus.py"]


def _rows(path: str) -> list[dict]:
    return [json.loads(l) for l in (CORPUS / path).read_text(encoding="utf-8").splitlines() if l.strip()]


def test_generated_entries_present():
    assert {e["path"] for e in ENTRIES} == {
        *(f"colloquial/{l}.jsonl" for l in ("ja", "en", "vi", "th")),
        "mojibake/ja.jsonl", "mojibake/vi.jsonl", "mixed/ja.jsonl", "mixed/en.jsonl"}


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["path"])
def test_count_and_unmeasured(entry):
    assert entry["count"] >= 300
    assert entry["ai_roundtrip"] == "未測定"
    rows = _rows(entry["path"])
    assert all(r["bytes"] == len(r["text"].encode("utf-8")) for r in rows)


@pytest.mark.parametrize("path", ["mojibake/ja.jsonl", "mojibake/vi.jsonl"])
def test_mojibake_pairs(path):
    for r in _rows(path):
        assert r["orig"] != r["text"]
        assert r["orig_id"].startswith(f"cv-{r['lang']}-")


def test_tatoeba_colloquial_rows():
    rows = [r for r in _rows("tatoeba/ja.jsonl") if r.get("register") == "colloquial"]
    assert len(rows) >= 300
    assert all(r["url"] == f"https://tatoeba.org/sentences/show/{r['id'].split(':')[1]}" and r["author"] for r in rows)


def test_tier_thresholds():
    import build_corpus as bc
    assert bc.tier("短い文です。") == "short"
    assert bc.tier("あ" * 200) == "short"
    assert bc.tier("あ" * 201) == "medium"
    assert bc.tier("一文目です。二文目です。") == "medium"
    assert bc.tier("文。" * 6) == "long"
    assert bc.tier("a" * 1001) == "long"
    assert bc.tier("Version 3.14 is out.") == "short"


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["path"])
def test_rows_use_tier_function(entry):
    import build_corpus as bc
    for r in _rows(entry["path"]):
        assert r["tier"] == bc.tier(r.get("orig", r["text"]))


def test_mojibake_ja_size_and_count():
    p = CORPUS / "mojibake" / "ja.jsonl"
    assert len(_rows("mojibake/ja.jsonl")) == 400
    assert p.stat().st_size <= 256 * 1024
