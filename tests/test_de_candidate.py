"""German (de) candidate + de-over-nl tie rule (tokens → utf8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
BANK = json.loads((ROOT / "TesseraTalk/fixtures/tense_matrix.json").read_text(encoding="utf-8"))
REPORT = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))
BY_SRC = {e["from"][0]: e for e in BANK["entries"]}


def _t():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


def test_de_in_tense_langs():
    t = _t()
    assert "de" in t.FINAL_TENSE_LANGS and "de" in t.FINAL_TENSE_MATRIX_LANGS


@pytest.mark.parametrize("s,want", [("I came", "kam"), ("he came", "kam"), ("she came", "kam")])
def test_de_strictly_wins_kam(s, want):
    assert _t().apply_es_fr_tense(s) == want
    assert BY_SRC[s]["lang"] == "de"


@pytest.mark.parametrize(
    "s,want",
    [("he thinks", "denkt"), ("we think", "denken"), ("they think", "denken"), ("we found", "fanden"),
     ("they found", "fanden"), ("he found", "fand"), ("we thought", "dachten"), ("you think", "denkt")],
)
def test_tie_goes_to_de(s, want):
    assert BY_SRC[s]["to"] == want and BY_SRC[s]["lang"] == "de"
    assert _t().apply_es_fr_tense(s) == want


def test_hand_bank_tie_goes_to_de():
    t = _t()
    assert t.apply_es_fr_tense("I found") == "fand"


@pytest.mark.parametrize(
    "s,want",
    [("I want", "wil"), ("I come", "kom"), ("you went", "ging"), ("he took", "nam"),
     ("we wanted", "wilden"), ("I take", "neem"), ("I think", "denk")],
)
def test_nl_kept_where_strictly_cheaper(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_de_will_rejected_by_homograph_guard():
    t = _t()
    assert t.en_homograph_tokens("will")
    for s in ("he wants", "I want", "who wants"):
        assert "will" not in t.apply_es_fr_tense(s).split()
    cell = next(c for c in REPORT["cells"] if c["src"] == "he wants")
    assert any(h["form"] == "will" for h in cell.get("homograph_dropped", []))


def test_compounds_nl_kept_when_cheaper():
    t = _t()
    assert t.apply_zh_de_phrases("swimming pool") == "zwembad"
    assert t.apply_zh_de_phrases("washing machine") == "wasmachine"


def test_prefer_on_tie_only_de_over_nl():
    t = _t()
    m = lambda r: (t.estimate_tokens(r), len(r.encode()))  # noqa: E731
    assert t.prefer_on_tie(("vond", "nl"), [("vond", "nl"), ("fand", "de")], m) == ("fand", "de")
    assert t.prefer_on_tie(("wil", "nl"), [("wil", "nl"), ("nahm", "de")], m) == ("wil", "nl")
    assert t.prefer_on_tie(("vis", "fr"), [("vis", "fr"), ("sah", "de")], m) == ("vis", "fr")


def test_no_formal_sie_for_you():
    for e in BANK["entries"]:
        if e["subject"] == "2" and e["lang"] == "de":
            assert e["to"] not in {"denken", "kommen", "fanden", "wollen", "kamen"}


def test_de_plain_tie_vs_romance_uses_normal_order():
    # sah (1 tok / 3 B) ties fr vis / es vio; normal token → utf8 → len → form order picks sah.
    assert _t().apply_es_fr_tense("I saw") == "sah"
