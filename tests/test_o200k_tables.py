"""o200k 実測表: 校正表の再現性と docs/o200k-lookup 参照表の形状。

- estimate_calibration: The committed o200k calibration table is reproducible and generalises.
- o200k_lookup
- o200k_notations_lookup: Sanity checks for docs/o200k-lookup/notations reference tables.
- o200k_weak_scripts: 弱支援スクリプト o200k 実測表の形状固定。出典 Tatoeba CC BY 2.0 FR。
"""

from __future__ import annotations

from pathlib import Path
import gzip
import hashlib
import importlib.util
import json


# ──── estimate_calibration ────────────────────────────────────────

"""The committed o200k calibration table is reproducible and generalises."""


ROOT = Path(__file__).resolve().parents[1]


def _cal():
    spec = importlib.util.spec_from_file_location("calibrate_estimate", ROOT / "scripts/calibrate_estimate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_calib_file_is_regenerated():
    mod = _cal()
    committed = json.loads(mod.CALIB.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(mod.build(), ensure_ascii=False))


def test_calib_matches_wordlist():
    mod = _cal()
    d = json.loads(mod.CALIB.read_text(encoding="utf-8"))
    assert d["wordlist_sha256"] == hashlib.sha256(mod.WORDLIST.read_bytes()).hexdigest()


def test_heldout_and_natural_agreement_floors():
    r = _cal().report()
    # held-out matrix cells (sha1(src) % 5 == 0) never feed the tables
    # miss-count floor: dropped cells shrink the held-out pool, not accuracy
    assert r["heldout"]["n"] - r["heldout"]["exact"] <= 7 and r["heldout"]["n"] >= 530
    assert r["heldout"]["flips"] == 0
    # independent natural sentences (not drawn from any bank); main scored 2/60
    assert r["natural"]["n"] == 60 and r["natural"]["exact"] >= 32
    assert r["natural"]["abs_err"] <= 56


# ──── o200k_lookup ────────────────────────────────────────────────

D = Path(__file__).resolve().parents[1] / "docs" / "o200k-lookup"


def _load(name):
    lines = (D / name).read_text(encoding="utf-8").rstrip("\n").split("\n")
    return json.loads(lines[0])["_meta"], {r["cp"]: r for r in map(json.loads, lines[1:])}


def test_emoji_table():
    meta, t = _load("emoji.jsonl")
    assert meta["emoji"] == "18.0" and meta["enc"] == "o200k_base"
    assert len(t) == 5244
    assert t["1F600"]["o"] == 1 and t["2764 FE0F"]["o"] == 1
    assert all(r["d"] == r["e"] - r["o"] and r["o"] >= 1 for r in t.values())


def test_specials_table():
    meta, t = _load("specials.jsonl")
    assert len(t) >= 6000
    assert t["2192"]["o"] == 1 and t["0085"]["o"] == 2
    assert all(r["d"] == r["e"] - r["o"] and r["b"] == len(r["s"].encode()) for r in t.values())


def test_cheap_symbols_table():
    lines = (D / "cheap-symbols.jsonl").read_text(encoding="utf-8").rstrip("\n").split("\n")
    rows = [json.loads(x) for x in lines[1:]]
    assert len(rows) == 40442
    assert sum(r["enc"] == "o200k" for r in rows) == 13491
    assert all(r["n"] == len(r["ids"]) for r in rows)


# ──── o200k_notations_lookup ──────────────────────────────────────

"""Sanity checks for docs/o200k-lookup/notations reference tables."""


D_o200k_notations_lookup = Path(__file__).resolve().parents[1] / "docs" / "o200k-lookup" / "notations"


EXPECTED = {
    "kaomoji-ja-o200k.jsonl": 37_515,
    "emoticons-ascii-o200k.jsonl": 485,
    "kaomoji-i18n-o200k.jsonl": 530,
    "legacy-notations-o200k.jsonl": 10_832,
}


def _count(path: Path, *, gz: bool = False) -> int:
    opener = gzip.open if gz else open
    n = 0
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            json.loads(line)
            n += 1
    return n


def test_plain_jsonl_counts() -> None:
    for name, expected in EXPECTED.items():
        assert _count(D_o200k_notations_lookup / name) == expected, name


def test_gzip_jsonl_counts() -> None:
    assert _count(D_o200k_notations_lookup / "self-kaomoji-notations-o200k.jsonl.gz", gz=True) == 64_564
    assert _count(D_o200k_notations_lookup / "self-extra-notations-o200k.jsonl.gz", gz=True) == 21_681


def test_readme_and_sources_present() -> None:
    assert (D_o200k_notations_lookup / "README.md").is_file()
    assert (D_o200k_notations_lookup / "self-notations-sources").is_dir()
    assert (D_o200k_notations_lookup / "self-extra-sources").is_dir()
    assert (D_o200k_notations_lookup / "kaomoji-i18n-emoticon-MIT-LICENSE.txt").is_file()


# ──── o200k_weak_scripts ──────────────────────────────────────────

"""弱支援スクリプト o200k 実測表の形状固定。出典 Tatoeba CC BY 2.0 FR。"""


F = Path(__file__).resolve().parents[1] / "docs" / "o200k-lookup" / "weak-scripts" / "weak-scripts.jsonl"


def test_weak_scripts_table():
    lines = F.read_text(encoding="utf-8").rstrip("\n").split("\n")
    meta = json.loads(lines[0])["_meta"]
    rows = [json.loads(x) for x in lines[1:]]
    assert meta["enc"] == "o200k_base" and "CC BY 2.0 FR" in meta["source"]
    assert len(rows) == 42 and len(meta["summary"]) == 14
    for r in rows:
        assert r["license"] == "CC BY 2.0 FR"
        assert r["url"] == f"https://tatoeba.org/sentences/show/{r['id']}"
        assert r["b"] == len(r["s"].encode()) and r["owner"]
    s = {x["lang"]: x for x in meta["summary"]}
    assert s["bo"]["o"] == 120 and s["am"]["o"] == 86 and s["ar"]["o"] == 38
    assert not any(x["abnormally_cheap"] for x in s.values())
    assert all(x["status"] == "examples_not_registered" for x in s.values())
