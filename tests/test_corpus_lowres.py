"""Consistency checks for the ko/vi/th/id/tr/he/fa/sw/bn/ta corpus samples."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "corpus"
SCRIPT = ROOT / "scripts" / "fetch_corpus_lowres.py"
ALLOWED = {"CC0-1.0", "CC-BY-2.0-FR", "CC-BY-4.0", "CC-BY-SA-4.0"}


def _load_script():
    spec = importlib.util.spec_from_file_location("fetch_corpus_lowres", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_script()
MINE = {f"{c}/{l}.jsonl" for c in MOD.CATEGORIES for l in MOD.LANGS}


def _entries():
    doc = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    return {e["path"]: e for e in doc["entries"] if e["path"] in MINE}


def test_manifest_covers_every_lang_and_category():
    assert set(_entries()) == MINE


@pytest.mark.parametrize("path", sorted(MINE))
def test_sample_matches_manifest(path):
    entry = _entries()[path]
    blob = (CORPUS / path).read_bytes()
    assert hashlib.sha256(blob).hexdigest() == entry["sha256"]
    rows = [json.loads(line) for line in blob.decode("utf-8").splitlines()]
    assert len(rows) == entry["count"] > 0
    assert sum(len(r["text"].encode("utf-8")) for r in rows) == entry["text_bytes"]
    cat, lang = path[:-len(".jsonl")].split("/")
    assert entry["license"] in ALLOWED
    assert entry["full_count"] >= 400 or (cat, lang) == ("short", "ta")
    assert entry["full_count"] >= entry["count"]
    for r in rows:
        assert (r["lang"], r["category"]) == (lang, cat)
        assert r["license"] == entry["license"] and r["text"].strip() == r["text"] != ""
        if cat == "short":
            assert len(r["text"]) <= MOD.SHORT_MAX_CHARS
    assert len({r["id"] for r in rows}) == len(rows)


def test_upstreams_are_sha256_pinned_https():
    pins = [MOD.FLORES_SHA256] + [sha for _, sha in MOD.TATOEBA.values()]
    assert all(re.fullmatch(r"[0-9a-f]{64}", p) for p in pins)
    assert set(MOD.TATOEBA) == set(MOD.FLORES) == set(MOD.LANGS)
    assert MOD.FLORES_URL.startswith("https://") and MOD.TATOEBA_URL.startswith("https://")


def test_fetch_rejects_sha256_mismatch(tmp_path):
    (tmp_path / ("0" * 64)).write_bytes(b"tampered")
    with pytest.raises(SystemExit, match="sha256 mismatch"):
        MOD.fetch("https://example.invalid/x", "0" * 64, tmp_path)


def test_jsonl_is_stable_and_key_ordered():
    rows = [{"text": "สวัสดี", "source": "s", "license": "CC-BY-SA-4.0",
             "id": "short-th-0000", "lang": "th", "category": "short", "extra": 1}]
    out = MOD.to_jsonl(rows).decode("utf-8")
    assert out == ('{"id": "short-th-0000", "lang": "th", "category": "short", '
                   '"text": "สวัสดี", "source": "s", "license": "CC-BY-SA-4.0"}\n')
