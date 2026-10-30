"""Stative verbs (know/have/want): EN present perfect is often continuative,
so simple-preterite readings (de wusste/hatten, nl wilde/wisten, es supe, pt
quis/tive) must not stand for it; EN `you` cells avoid sg/pl-marked forms."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BANK = json.loads((ROOT / "TesseraTalk/fixtures/tense_matrix.json").read_text(encoding="utf-8"))
BY_SRC = {e["from"][0]: e for e in BANK["entries"]}
REPORT = {c["src"]: c for c in json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]}
STATIVE = ("known", "had", "wanted")
PRETERITE = {"wusste", "hatten", "wollte", "wussten", "wist", "wisten", "wilde", "wilden", "had", "hadden",
             "supe", "supo", "supimos", "quis", "quisemos", "tive", "teve", "tivemos", "tiveram", "quiseram"}


def _perf_cells():
    return [c for c in REPORT.values() if c["tense"] == "perf" and c["verb"] in ("know", "have", "want")]


def test_no_stative_preterite_in_perf():
    cells = _perf_cells()
    assert cells
    for c in cells:
        if c["status"] == "adopt":
            assert c.get("shape") != "simple-preterite", c["src"]
            assert c["best"].split()[-1] not in PRETERITE, c["src"]


@pytest.mark.parametrize("src,form", [
    ("you have known", "avoir su"), ("you have had", "avoir eu"), ("you have wanted", "avoir voulu"),
])
def test_you_stative_perfect_uses_infinitive(src, form):
    assert BY_SRC[src]["to"] == form
    assert BY_SRC[src]["lang"] == "fr"


@pytest.mark.parametrize("src", ["he has known", "she has had", "it has wanted", "who has known"])
def test_stative_sg3_falls_back_to_en(src):
    assert src not in BY_SRC
    assert REPORT[src]["status"] == "reject"


def test_candidates_module_level():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tm", ROOT / "scripts/tense_matrix.py")
    tm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tm)
    conj = json.loads(tm.CONJ_PATH.read_text(encoding="utf-8"))["conj"]
    forms = {(c["form"], c["lang"]) for c in tm._candidates(conj, "1s", "perf", "know", "")}
    assert ("habe gewusst", "de") in forms and ("heb geweten", "nl") in forms
    assert ("wusste", "de") not in forms and ("supe", "es") not in forms
    you = tm._candidates(conj, "2", "perf", "have", "")
    assert {c["form"] for c in you if c["lang"] in ("es", "it", "fr", "de", "nl")} == {"avoir eu"}
    # non-stative verbs keep the preterite policy
    go = {(c["form"], c["lang"]) for c in tm._candidates(conj, "1s", "perf", "find", "")}
    assert ("fand", "de") in go


def test_you_infinitive_is_person_neutral():
    for src in ("you have known", "you have had", "you have wanted"):
        assert REPORT[src]["number"] == "2-neutral"


def test_you_infinitive_candidate_tag():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tm2", ROOT / "scripts/tense_matrix.py")
    tm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tm)
    conj = json.loads(tm.CONJ_PATH.read_text(encoding="utf-8"))["conj"]
    fr = [c for c in tm._candidates(conj, "2", "perf", "know", "") if c["lang"] == "fr"]
    assert fr == [{"form": "avoir su", "lang": "fr", "shape": "inf-perfect", "number": "2-neutral"}]
