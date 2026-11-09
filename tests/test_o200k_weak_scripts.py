"""弱支援スクリプト o200k 実測表の形状固定。出典 Tatoeba CC BY 2.0 FR。"""
import json
from pathlib import Path

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
