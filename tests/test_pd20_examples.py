"""PD corpus 20 examples + subject/aux contraction axis + el cheapest winners.

Expectations are the CURRENT pipeline output (not aspirational). Desired short
forms that are not produced yet are xfail(strict=True) with a reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
FIX = json.loads((ROOT / "tests/fixtures/pd20_examples.json").read_text(encoding="utf-8"))
ENTRIES = FIX["entries"]
PD = ROOT / "tests/fixtures/pd_corpus"


def _t():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


def _lp():
    return _load("lex_policy", "shared/lex_policy.py")


@pytest.mark.parametrize("e", ENTRIES, ids=[e["id"] for e in ENTRIES])
def test_pd20_text_is_cut_from_corpus(e):
    assert e["text"] in (PD / e["source"]).read_text(encoding="utf-8")


@pytest.mark.parametrize("e", ENTRIES, ids=[e["id"] for e in ENTRIES])
def test_pd20_current_output_and_invariants(e):
    t = _t()
    src = e["text"]
    out = t.final_token_pass(src)
    assert out == e["expect"]
    assert t.final_token_pass(src) == out  # deterministic
    assert t.estimate_tokens(out) <= t.estimate_tokens(src)
    if e["kind"] == "keep":
        assert out == src
    for bad in ("voy", "vou", "Bahnhof", "iré"):
        if bad not in src:
            assert bad not in out, bad


_ASPIRATIONAL = [e for e in ENTRIES if e.get("want_contains")]


@pytest.mark.parametrize(
    "e",
    [
        pytest.param(e, marks=pytest.mark.xfail(strict=True, reason=e["xfail_reason"])) if e.get("xfail_reason") else e
        for e in _ASPIRATIONAL
    ],
    ids=[e["id"] for e in _ASPIRATIONAL],
)
def test_pd20_desired_short_form(e):
    assert e["want_contains"] in _t().final_token_pass(e["text"])


# --- subject + auxiliary contractions (C) vs B-final ------------------------

@pytest.mark.parametrize(
    "src,want",
    [
        ("I will go", "I'll go"),
        ("I have gone", "I've gone"),
        ("I am here", "I'm here"),
        ("I would go", "I'd go"),
        ("we are here", "we're here"),
        ("they are here", "they're here"),
        ("he is here", "he's here"),
    ],
)
def test_c_contractions_shrink(src, want):
    t = _t()
    out = _lp().apply_en_contractions(src)
    assert out == want
    assert t.estimate_tokens(out) <= t.estimate_tokens(src)
    assert len(out.encode()) < len(src.encode())


@pytest.mark.parametrize(
    "full,short,winner",
    [
        ("I will go", "I'll go", "vou"),
        ("I am going", "I'm going", "vou"),
        ("I will take it", "I'll take it", "πάρω it"),
    ],
)
def test_b_final_accepts_full_and_contracted(full, short, winner):
    t = _t()
    assert t.apply_es_fr_tense(full) == winner
    assert t.apply_es_fr_tense(short) == winner
    # C then B (pipeline order) lands on the same subject-dropped form
    assert t.apply_es_fr_tense(_lp().apply_en_contractions(full)) == winner


@pytest.mark.parametrize(
    "full,short",
    [
        ("I will find it", "I'll find it"),
        ("I would go", "I'd go"),
        ("we will go", "we'll go"),
    ],
)
def test_b_final_contracted_matches_full(full, short):
    t = _t()
    assert t.apply_es_fr_tense(short) == t.apply_es_fr_tense(full)


@pytest.mark.xfail(strict=True, reason="I'm going to <V> 未登録の動詞(buy)は going-to 未変換（誤食しないのは正）")
def test_going_to_buy_contracted():
    assert _t().apply_es_fr_tense("I'm going to buy") != "I'm going to buy"


def test_going_to_guard_contracted():
    t = _t()
    out = t.apply_es_fr_tense("I'm going to buy")
    assert "vou" not in out and "voy" not in out


# --- Greek (el) runtime winners ---------------------------------------------

@pytest.mark.parametrize(
    "src,el",
    [
        ("I will take", "πάρω"),
        ("I'll take", "πάρω"),
        ("I am going to take", "πάρω"),
        ("I will find", "βρω"),
        ("I'll find", "βρω"),
    ],
)
def test_el_wins_cheapest(src, el):
    t = _t()
    out = t.apply_es_fr_tense(src)
    assert out == el
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_bank_to_label_matches_runtime_winner():
    t = _t()
    bank = json.loads((ROOT / "TesseraTalk/fixtures/es_fr_tense.json").read_text(encoding="utf-8"))
    langs = set()
    for e in bank["entries"]:
        assert t.apply_es_fr_tense(e["from"][0]) == e["to"], e["id"]
        langs.add(e["lang"])
    assert "el" in langs
