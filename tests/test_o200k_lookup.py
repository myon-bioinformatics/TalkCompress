import json
from pathlib import Path

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
