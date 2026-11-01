"""tests/fixtures/corpus の manifest とファイルの整合を確かめる。"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib

import pytest

CORPUS = pathlib.Path(__file__).parent / "fixtures" / "corpus"
MANIFEST = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
FILES = MANIFEST["files"]
FREE = {"CC0-1.0", "CC-BY-2.0-FR"}
FIELDS = {"id", "text", "lang", "tier", "source", "license", "author", "url"}


def _rows(entry):
    return [json.loads(l) for l in (CORPUS / entry["path"]).read_text(encoding="utf-8").split("\n") if l]


def test_manifest_lists_every_jsonl():
    on_disk = {p.relative_to(CORPUS).as_posix() for p in CORPUS.rglob("*.jsonl")}
    assert on_disk == {e["path"] for e in FILES}


@pytest.mark.parametrize("entry", FILES, ids=lambda e: e["path"])
def test_sha_count_bytes(entry):
    p = CORPUS / entry["path"]
    assert hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"]
    rows = _rows(entry)
    assert len(rows) == entry["count"]
    assert entry["count"] >= 300
    assert all(r["bytes"] == len(r["text"].encode("utf-8")) for r in rows)
    assert sum(r["bytes"] for r in rows) == entry["bytes_total"]
    assert sum(r["o200k"] for r in rows) == entry["o200k_total"]
    assert len({r["text"] for r in rows}) == len(rows)


@pytest.mark.parametrize("entry", FILES, ids=lambda e: e["path"])
def test_license_and_roundtrip_note(entry):
    assert entry["sources"] and all(s["license"] in FREE for s in entry["sources"])
    for s in entry["sources"]:
        if s["license"].startswith("CC-BY"):
            assert s["attribution"]
    assert entry["ai_roundtrip"] == "未測定"


def test_mojibake_pairs_differ():
    for entry in (e for e in FILES if e["category"] == "mojibake"):
        assert all(r["orig"] != r["text"] for r in _rows(entry))


@pytest.mark.skipif(os.environ.get("TALKCOMPRESS_RUN_TOKENIZER_CHECKS") != "1", reason="tokenizer 取得が必要なため opt-in")
@pytest.mark.parametrize("entry", FILES, ids=lambda e: e["path"])
def test_o200k_recount(entry):
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    assert all(len(enc.encode(r["text"])) == r["o200k"] for r in _rows(entry))


def test_no_duplicate_entries():
    paths = [e["path"] for e in FILES]
    assert len(paths) == len(set(paths))
    keys = [(e["category"], e["lang"], tuple(s["name"] for s in e["sources"])) for e in FILES]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("entry", FILES, ids=lambda e: e["path"])
def test_record_fields(entry):
    assert entry["path"] == f"{entry['category']}/{entry['lang']}.jsonl"
    rows = _rows(entry)
    assert len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        assert FIELDS <= r.keys()
        assert r["lang"] == entry["lang"]
        assert r["tier"] in {"short", "medium", "long"}
        assert r["license"] in FREE
        assert r["source"]
        if r["source"].startswith(("common-voice:", "tatoeba:")):
            assert r["url"]


def test_ids_unique_across_files():
    ids = [r["id"] for e in FILES for r in _rows(e)]
    assert len(ids) == len(set(ids))
